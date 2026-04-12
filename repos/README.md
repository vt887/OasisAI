# Mount local git repositories for the indexer

Place local (cloned) Git repositories as sub-directories under this
`repos/` directory so the indexer can discover and index them.

Layout example:

repos/
  myproject/         # a cloned git repository
  another-repo/      # another cloned git repository

HOST_PROJECTS_ROOT
-------------------

The indexer expects the host path where repositories are mounted to be
provided when triggering an indexing run. By default the indexer will
look in this `repos/` directory. If this directory is empty (for
example when you keep repositories elsewhere on the host), you can set
the `HOST_PROJECTS_ROOT` variable instead — the `Makefile` exposes this
variable and it defaults to `/workspace`.

When you run the helper target to index everything, the chosen path is
sent to the indexer as the `repos_root` in the JSON payload. You can
override `HOST_PROJECTS_ROOT` from the environment or on the `make`
command line.

Examples
--------

Use the default value (/workspace):

HOST_PROJECTS_ROOT is set in the Makefile by default; simply run:

```sh
make index all
```

Override with an environment variable:

```sh
HOST_PROJECTS_ROOT=/path/on/host make index all
```

Or pass it as a make variable:

```sh
make index all HOST_PROJECTS_ROOT=/path/on/host
```

If you are running the full Docker compose stack, ensure the host path
you provide is bind-mounted into the relevant container (or otherwise
available to the indexer process) so the service can access the
repositories to index them.

For more details see the project `Makefile` and the indexer service
documentation.
