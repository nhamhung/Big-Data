function return_percentage () {
	percent=$(echo "scale=2; $1 * 100 / $2" | bc)

	echo $percent
}

return_result=$(return_percentage 80 100)
echo "80 out of 100 is $return_result%"
