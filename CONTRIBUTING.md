
Le code est linté et les imports trié avec [Ruff](https://docs.astral.sh/ruff/) :
```bash
ruff check --fix --select I .
```


Ruff s'intégre dans la plupart des éditeurs de code. Vous pouvez automatiser le linter avec les _hooks_ de _pre-commit_ de git si vous préférez :
```bash
pre-commit install
``
