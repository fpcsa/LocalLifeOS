# Native launcher

After installing backend and frontend dependencies, run through the platform wrapper:

```powershell
.\scripts\locallife.ps1 doctor
.\scripts\locallife.ps1 start --open-browser
```

```sh
./scripts/locallife.sh doctor
./scripts/locallife.sh start --open-browser
```

Installing `apps/api` as a Python package also exposes the same `locallife` console command.

| Command | Behavior |
| --- | --- |
| `locallife start` | Checks ports, starts API/web on `127.0.0.1`, waits for health, writes PID state/logs |
| `locallife stop` | Stops only processes recorded by the launcher and removes PID state |
| `locallife status` | Shows PIDs, reachability, loopback URLs, network mode, and data directory |
| `locallife backup` | Initializes/migrates data, creates and verifies a full backup; `--encrypt` prompts securely |
| `locallife restore FILE` | Requires stopped services, verifies/previews, confirms, safety-backs up, restores |
| `locallife doctor` | Checks Python/Node/dependencies, native bind, data write, database/schema, and ports |

`start` uses a production Next build when present and otherwise uses the development server. It
opens a browser only with `--open-browser`. `backup --password-file PATH` and
`restore --password-file PATH` support non-interactive local automation without putting a password
in shell history or the process list. Protect and delete password files using OS facilities.
