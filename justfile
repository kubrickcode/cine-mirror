set dotenv-load := true

root_dir := justfile_directory()

deps: deps-root

deps-root:
    pnpm install

kill-port port:
    #!/usr/bin/env bash
    set -euo pipefail
    pid=$(ss -tlnp | grep ":{{ port }} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
    if [ -n "$pid" ]; then
        echo "Killing process $pid on port {{ port }}"
        kill -9 $pid
    else
        echo "No process found on port {{ port }}"
    fi

lint target="all":
    #!/usr/bin/env bash
    set -euox pipefail
    case "{{ target }}" in
      all)
        just lint justfile
        just lint config
        ;;
      justfile)
        just --fmt --unstable
        ;;
      config)
        npx prettier --write "**/*.{json,yml,yaml,md}"
        ;;
      *)
        echo "Unknown target: {{ target }}"
        exit 1
        ;;
    esac

# data-collector 명령어 (dc- prefix)
dc +args:
    just --justfile {{ root_dir }}/data-collector/justfile {{ args }}

dc-run:
    just dc run

dc-run-small:
    just dc run-small

dc-sync:
    just dc sync

dc-migrate:
    just dc migrate

dc-test *args:
    just dc test {{ args }}

dc-lint:
    just dc lint

dc-lint-fix:
    just dc lint-fix

# core-film-journal 명령어 (cfj- prefix)
cfj +args:
    just --justfile {{ root_dir }}/core-film-journal/justfile {{ args }}

cfj-sync:
    just cfj sync

cfj-migrate:
    just cfj migrate

cfj-run:
    just cfj run

cfj-test *args:
    just cfj test {{ args }}

cfj-lint:
    just cfj lint

cfj-lint-fix:
    just cfj lint-fix

sync-agents:
    bash scripts/sync-agents.sh

typecheck-file file:
    #!/usr/bin/env bash
    set -euo pipefail
    dir=$(dirname "{{ file }}")
    while [[ "$dir" != "." && "$dir" != "/" ]]; do
      if [[ -f "$dir/tsconfig.json" ]]; then
        (cd "$dir" && npx tsc --noEmit --incremental)
        exit 0
      fi
      dir=$(dirname "$dir")
    done
    if [[ -f "tsconfig.json" ]]; then
      npx tsc --noEmit --incremental
    fi
