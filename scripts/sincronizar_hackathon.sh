#!/usr/bin/env bash
# Avanza la entrega al mismo commit de Grifter sin reescribir el historial.
# Los argumentos permiten comprobar el comportamiento con repositorios locales.
set -euo pipefail

repositorio_origen="${1:-https://github.com/mgtapia/grifter.git}"
repositorio_destino="${2:-origin}"

git fetch --no-tags --no-recurse-submodules "$repositorio_origen" \
  'refs/heads/main:refs/remotes/grifter/main'
git fetch --no-tags --no-recurse-submodules "$repositorio_destino" \
  'refs/heads/main:refs/remotes/entrega/main'

origen=$(git rev-parse refs/remotes/grifter/main)
destino=$(git rev-parse refs/remotes/entrega/main)

if [[ "$origen" == "$destino" ]]; then
  printf 'Grifter y la entrega ya están en %s.\n' "$origen"
  exit 0
fi

if ! git merge-base --is-ancestor "$destino" "$origen"; then
  printf 'La entrega tiene commits que no están en Grifter. Integra su main mediante un PR en Grifter antes de sincronizar.\n' >&2
  exit 1
fi

git push "$repositorio_destino" "$origen:refs/heads/main"
printf 'Entrega actualizada al commit %s de Grifter.\n' "$origen"
