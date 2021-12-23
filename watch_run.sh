#!/bin/bash
#
# Watch file specified and run Python process every time the file is changed
# Helpful during development to test new changes automatically
#
# Requires 'entr' script:
# > sudo apt-get install entr
#

if [[ $# < 1 ]]
then
	echo "Usage: $0 file.py [args]"
	exit 1
else
	file=$1
	shift
fi

ls $file | entr python3 $file "$@"

