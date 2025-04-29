# top4grep
A grep tool for the top 4 security conferences

## Installation
```
git clone https://github.com/Kyle-Kyle/top4grep
cd top4grep
pip3 install .
```

## Usage 
### Database Initialization
If you want to update the papers stored in `top4grep/papers.db`, you can recreate it with:
```bash
top4grep --build-db --abstracts
```

Make sure to install the database build requirements too when building/updating the database: `pip3 install .[BUILD]`.

### Query
```bash
top4grep -k <keywords>
```

For example, `python top4grep.py -k linux,kernel`
Currently, the query is just a case-insensitive match (just like grep). The returned results must contains all the input keywords (papers containing keyword1 AND keyword2 AND ...). Support for `OR` operation (papers containing keyword1 OR keyword2) is missing, but will be added in the future.

Add `--abstracts` to print the abstracts too.

## Screenshot
![screenshot](https://raw.githubusercontent.com/Kyle-Kyle/top4grep/master/img/screenshot.png)

## TODO
- [x] grep in abstract
- [ ] fuzzy match
- [ ] complex search logic (`OR` operation)
