default:
    just list

prep-data:
    python scripts/prepare.py

matchit: prep-data
    Rscript scripts/matcher.R

up:
    # start metamap servers
    ~/public_mm/bin/wsdserverctl start
    ~/public_mm/bin/skrmedpostctl start

down:
    # stop metamap servers
    ~/public_mm/bin/wsdserverctl stop
    ~/public_mm/bin/skrmedpostctl stop

run-metamap: prep-data
    just up
    sleep 60
    python scripts/run_metamap.py
    just down
    sleep 60
    python scripts/parse_metamap.py

run:
  python $(fd -e py | fzf)
