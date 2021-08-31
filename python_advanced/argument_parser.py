import argparse

def get_args():
    parser = argparse.ArgumentParser(description="Mutually exclusive parser", epilog="Example usage: ... ")

    group = parser.add_mutually_exclusive_group()
    
    # include both long and short options
    group.add_argument("-x", "--execute", action="store", help="To execute some parameter")

    group.add_argument("-e", "--evaluate", help="Another mutually exclusive option such as quite mode")

    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    print(args)

# Extensions: add_argument() parameters such as default, type, choices. Other utilities such as sub-commands...
