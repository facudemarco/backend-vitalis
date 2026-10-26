# Datos personales: estudios y sector

Antes de desplegar esta versión, ejecutar manualmente en MariaDB el archivo
`medical-record-education-sector.sql`. Agrega dos columnas anulables en
`medical_record_data` y puede ejecutarse de nuevo sin recrear columnas.
No altera los valores guardados en fichas anteriores.

`education_level` acepta Primarios, Secundarios o Terciarios. El formulario exige
seleccionar una opción al guardar datos personales. La API admite campos ausentes
o nulos para seguir leyendo y actualizando fichas antiguas, y rechaza otras opciones.
`sector` admite texto de hasta 255 caracteres.

La impresión incluye Empresa, Estudios y Sector, manteniendo el formato de la ficha.
Se verificó con datos ficticios normales y textos largos, con y sin foto.

Admin y secretaría tienen controles para eliminar el estudio completo (incluidos
sus archivos e informes), un archivo del estudio o un informe individual.
Se solicita confirmación antes del borrado. Los endpoints existentes siguen
limitados a esos roles; empresas, pacientes y profesionales no pueden borrar.
Eliminar archivos no modifica automáticamente el estado de publicación del paciente,
que continúa bajo control de admin/secretaría.
