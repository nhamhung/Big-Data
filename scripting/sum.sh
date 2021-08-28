function sum_array () {
	local sum=0
	for number in "$@"
	do
		sum=$(echo "$sum + $number" | bc)
	done
	echo $sum
}

test_array=(14 12 15)
total=$(sum_array "${test_array[@]}")
echo "Total is $total"
