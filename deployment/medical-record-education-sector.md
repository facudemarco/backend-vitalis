# Datos personales: estudios y sector

Antes de desplegar esta versión, ejecutar manualmente en MariaDB el archivo
`medical-record-education-sector.sql`. Agrega dos columnas anulables en
`medical_record_data` y puede ejecutarse de nuevo sin recrear columnas.
No altera los valores guardados en fichas anteriores.

`education_level` acepta Primarios, Secundarios o Terciarios y es opcional.
La API admite campos ausentes, vacíos o nulos, y rechaza otras opciones.
`sector` admite texto de hasta 255 caracteres.

La impresión incluye Empresa, Estudios y Sector, manteniendo el formato de la ficha.
Se verificó con datos ficticios normales y textos largos, con y sin foto.
Estudios y Sector se ubican al final de los datos personales, en ese orden.
Tareas a realizar ya no aparece en el formulario ni en la impresión; sus valores
anteriores se conservan en la base de datos.

## Corrección del guardado

El 27/10 se constató por lectura del VPS que faltaban `education_level` y `sector`,
y que `phone` era `INT(11)`, insuficiente para teléfonos de diez dígitos como los
ingresados. Los logs mostraban múltiples POST con estado 500. No se reprodujeron
escrituras en producción para obtener un error SQL; el diagnóstico se basa en el
esquema real y la reproducción local del caso.

Ejecutar manualmente `medical-record-save-fix.sql` en la base correspondiente:
incluye las columnas faltantes y amplía `phone` a BIGINT sin cambiar los números.
No basta con volver a compilar los contenedores. Después, ejecutar desde la raíz
del backend `python -m deployment.check_medical_record_schema`. Este chequeo solo
lee metadatos y termina con código 1 si hay incompatibilidades; debe pasar antes
de habilitar la versión para usuarios.

El backend comprueba columnas y rangos antes de escribir archivos o registros.
Los errores de esquema devuelven 503 con código identificable; los de campos
devuelven 422. Los fallos inesperados registran tipo y código de error, sin volcar
los datos clínicos enviados. La pantalla distingue errores del servidor, validación,
sesión y conexión, y conserva el formulario para reintentar.

Admin y secretaría tienen controles para eliminar el estudio completo (incluidos
sus archivos e informes), un archivo del estudio o un informe individual.
Se solicita confirmación antes del borrado. Los endpoints existentes siguen
limitados a esos roles; empresas, pacientes y profesionales no pueden borrar.
Eliminar archivos no modifica automáticamente el estado de publicación del paciente,
que continúa bajo control de admin/secretaría.
