#!/bin/bash

config_source='/etc/testsys/poster-config.py'
config_file='/etc/testsys/poster-geterated.conf'
directory_data='/var/lib/testsys/poster'
directory_include='/home/burunduk3/poster'
directory_save='/srv/www/keep'
poster='/home/burunduk3/poster/poster.pl'

cd "$directory_save"

while true; do
  sleep 10
  date > "$directory_data/temporary_result"
  ok='true'
  if [ -f "$config_source" ] && [ "$config_source" -nt "$config_file" ]; then
    su - nobody -c "python '$config_source'" > "$directory_data/temporary_config" 2>&1 || ok='false'
    if [ "$ok" != 'true' ]; then
      echo 'fail in preparing config' >> "$directory_data/temporary_result"
      cat "$directory_data/temporary_config" >> "$directory_data/temporary_result"
      chgrp acm "$directory_data/temporary_result"
      mv "$directory_data/temporary_result" "$directory_data/result"
      continue
    fi
    chown nobody:acm "$config_source"
    mv "$directory_data/temporary_config" "$config_file"
  fi
  cat "$config_file" | while read -r line; do
    result_file=''
    params=''
    contest=''
    for token in $line; do
      if [ "$result_file" == '' ]; then
        contest="$token"
      else
        params="$params $result_file"
      fi
      result_file="$token"
    done
    perl -I"$directory_include" "$poster" $params > "$directory_data/temporary_monitor" 2>&1 || ok='false'
    if [ "$ok" != 'true' ]; then
      echo "$contest: fail: $(cat "$directory_data/temporary_monitor")" >> "$directory_data/temporary_result"
      continue
    fi
    chmod 0664 "$directory_data/temporary_monitor"
    # А теперь, наконец, зачем мы всё это время сидели в $directory_save вместо $directory_data:
    # монитор можно сохранить в файл, указав полный путь к этому файлу.
    mv "$directory_data/temporary_monitor" "$result_file"
    echo "$contest: ok" >> "$directory_data/temporary_result"
  done
  chgrp acm "$directory_data/temporary_result"
  mv "$directory_data/temporary_result" "$directory_data/result"
done

