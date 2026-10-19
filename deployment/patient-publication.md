# Publicación de empleados

El estado `Completado` es una aprobación manual exclusiva de administración y
secretaría. Para secretaría se rechaza si no hay estudios cargados, si alguno no está Disponible,
si falta su archivo o si falta un informe exigido por la categoría. El consentimiento
informado no requiere un informe adicional. Las categorías desconocidas requieren
informe por defecto. El mensaje de rechazo indica que debe hablar con un administrador.
Los administradores pueden autorizar Completado aunque falten estudios o informes;
esa excepción habilita al empleado y sus archivos existentes para la empresa.

La validación revisa los estudios registrados. Los paquetes de `study_type` son texto,
no una lista estructurada de estudios esperados: administración/secretaría debe
confirmar también que se cargaron todos los estudios solicitados antes de publicar.

Las empresas solo pueden listar y consultar empleados propios aprobados como
Completado. La aprobación manual es la fuente de verdad, también cuando un admin
autoriza una excepción. Los profesionales ven ese estado en verde. Volver a En
proceso oculta de nuevo al empleado y sus archivos para la empresa.

## Despliegue manual

1. Desplegar el backend y frontend. Se utiliza la columna `patients.patient_status`
   existente; no hay migraciones ni cambios a registros existentes.
2. Reemplazar en la configuración Nginx de Vitalis el bloque que sirve
   `studies/files/public/` con `nginx-study-files.conf`. Ese bloque envía las URL
   existentes al backend, que verifica la cookie de sesión y los permisos.
3. Validar Nginx y recargar su configuración siguiendo el procedimiento habitual.
4. Verificar con cuentas de empresa y personal los casos En proceso/Completado y
   la apertura de un enlace PDF. Sin sesión debe responder 401; una empresa no
   autorizada debe recibir 404. Un empleado autorizado debe poder ver sus archivos.

**El paso de Nginx es necesario:** mientras siga el `alias` anterior, un enlace PDF
conocido puede abrirse por fuera de los controles de la API. Las copias ya descargadas
o guardadas en la caché del navegador no pueden revocarse.
