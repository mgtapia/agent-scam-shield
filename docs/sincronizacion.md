# Sincronización de la entrega

El desarrollo se integra mediante PR en `mgtapia/grifter`, rama `main`. El repositorio `platanus-hack/platanus-hack-26-cl-team-40` consulta esa rama cada cinco minutos mediante GitHub Actions y avanza su propia `main` al mismo commit. GitHub puede retrasar las ejecuciones programadas: cinco minutos es la frecuencia solicitada, no un plazo máximo.

El workflow [sincronizar-hackathon.yml](../.github/workflows/sincronizar-hackathon.yml) solo ejecuta su trabajo en el repositorio de la hackathon. Usa el `GITHUB_TOKEN` temporal del destino con permiso `contents: write`; no requiere llaves personales ni secrets adicionales. Se puede ejecutar también desde la pestaña Actions, con **Run workflow** sobre `main`:

```bash
gh workflow run sincronizar-hackathon.yml --repo platanus-hack/platanus-hack-26-cl-team-40 --ref main
```

El script [sincronizar_hackathon.sh](../scripts/sincronizar_hackathon.sh) comprueba que el destino sea un ancestro del origen y hace un push normal. Si hay commits exclusivos de la entrega, falla y los conserva: primero hay que incorporarlos mediante un PR en Grifter. No crea commits de sincronización ni usa `push --force`.

## Dónde editar

Edita el código, la portada, `GUIA.md`, el logo y los metadatos de la hackathon en Grifter. Ambos repositorios comparten estos archivos para que los siguientes merges puedan copiarse sin conflictos. Las cifras detalladas y sus pruebas siguen en `GUIA.md`; `README.md` es la portada breve de la entrega.

Las pruebas se ejecutan en los PR y pushes de Grifter con `pruebas.yml`. GitHub no dispara otro workflow de push cuando quien actualiza el destino es su `GITHUB_TOKEN`; el resultado de CI del origen sigue disponible en Grifter.

## Cambios de workflows y recuperación

El token automático no tiene permiso para introducir workflows nuevos o modificados. Si un PR cambia `.github/workflows/`, publica primero su rama también en el repositorio de la hackathon (la configuración local de `origin` con dos URLs de push ya lo hace). GitHub admite el avance cuando esos archivos idénticos ya existen en otra rama del destino. Si un cambio de workflows se fusionó desde una rama que solo existía en Grifter, actualiza manualmente ambos repositorios desde una copia local con acceso y vuelve a ejecutar el workflow. No uses force para resolverlo.

Con la configuración local de dos destinos, `git push` sigue enviando la rama a ambos. La sincronización programada cubre también los merges realizados directamente en GitHub. Para mantener el historial común, los cambios de la entrega deben entrar por Grifter.

En repositorios públicos, GitHub desactiva los workflows programados tras 60 días sin actividad. Se pueden volver a habilitar desde Actions. Referencias: [eventos programados](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [alcance y eventos del GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token) y [permiso para workflows y excepción de otra rama](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).
