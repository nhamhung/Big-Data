case $1 in
Monday|Tuesday|Wednesday|Thursday|Friday)
	echo "Weekday";;
Saturday|Sunday)
	echo "Weekend";;
*)
	echo "Not a day!";;
esac
	
