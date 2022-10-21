#!/usr/bin/env bash
wdir=`dirname $0`
echo $wdir
/home/chris/.pyenv/versions/venv/bin/python $wdir/manage.py runserver
