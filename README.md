# malenia
#### Machine learning automatization package to ease experiments launching and results extraction

## Functionalities

#### Check condor errors:
Check if there is any error in your condor_output .err files.
- In an integrated terminal, with the malenia package installed in your python environnement, run:

```bash
malenia_check_condor_errors
```

#### Testing with pytest:
Check that the malenia package functionalities work properly (currently only support results extraction functionality tests, i.e. checks that results tables are being contructed without errors).
- In an integrated terminal, with the malenia package installed in your python environnement, run:

```bash
malenia_test
```
