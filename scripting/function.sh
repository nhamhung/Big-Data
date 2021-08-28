function what_day () {
	current_day=$(date | cut -d " " -f1)

	echo "Today is $current_day"
}

what_day
