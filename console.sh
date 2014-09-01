#!/bin/bash

target="acm.math.spbu.ru:17240"
case "`hostname`" in
    ('acm1') target="172.27.53.27:17240";;
esac

cd ~/code/testsys/
exec ./console.py -p ~/.ssh/testsys-console.pwd --msglevel=4 --name=burunduk3 "$target"

