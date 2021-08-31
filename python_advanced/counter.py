from collections import Counter

counter_one = Counter('superman')

print(counter_one)

counter_two = Counter('super')

print(counter_one.subtract(counter_two))

print(counter_one)
