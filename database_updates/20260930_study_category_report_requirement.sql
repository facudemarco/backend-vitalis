-- Ejecutar una sola vez en la base de datos Vitalis antes de desplegar el backend.
-- Las categorías existentes mantienen el comportamiento actual: informe obligatorio.
ALTER TABLE studies_admin
  ADD COLUMN IF NOT EXISTS requires_report TINYINT(1) NOT NULL DEFAULT 1;

-- Distingue el archivo original del estudio de un informe cargado al confirmarlo.
ALTER TABLE study_files
  ADD COLUMN IF NOT EXISTS is_report TINYINT(1) NOT NULL DEFAULT 0;

-- El flujo anterior guardaba los informes como el archivo más reciente, sin marcarlos.
-- Marcamos el último archivo de los estudios que tienen más de uno para preservar
-- los informes ya cargados y permitir confirmar estudios pendientes preexistentes.
UPDATE study_files AS sf
JOIN (
  SELECT id
  FROM (
    SELECT
      id,
      study_id,
      ROW_NUMBER() OVER (PARTITION BY study_id ORDER BY uploaded_at DESC, id DESC) AS file_order,
      COUNT(*) OVER (PARTITION BY study_id) AS file_count
    FROM study_files
  ) AS ranked_files
  WHERE file_order = 1 AND file_count > 1
) AS last_files ON last_files.id = sf.id
SET sf.is_report = 1;
