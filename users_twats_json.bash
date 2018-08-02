#!/usr/bin/env bash


rebuild_symlinks() {
	local i src
	for i in users/*/*; do
		if [[ -L "$i" ]]; then
			src=$(readlink "$i")
			#echo "source: '$src'"
			rm "$i"
			ln -s "../../data/${src##*/}" "$i"
		fi
	done

}


if ! [[ -e "users" ]]; then
	mkdir users

	for item in *; do
		## if directory, and not css, data or emoji
		if [[ -d $item && ! $item =~ ^(css|data|emoji)$ ]]; then
			## move user directory within the ./users/ dir
			mv -v "$item" users/
			## rename json file
			[[ -e users/$item/$item.json ]] && mv -v "users/${item}/${item}.json" "users/${item}/twats.json"
		fi
	done
	## rebuild symlinks
	rebuild_symlinks
fi
