from collections import ChainMap
import os
import argparse

def main():
    """
    ChainMap is especially useful when used to set up defaults. It goes through each map to find the first matching key and return the corresponding value. In this example, the precedence is as followed: argsparser > environment variables > default otions.
    """
    default = { 'username': 'admin', 'password': 'admin' }

    parser = argparse.ArgumentParser("Key in your login information from the CLI.")

    parser.add_argument("-u", "--username", help="Your username")
    parser.add_argument("-p", "--password", help="Your password")

    args = parser.parse_args() # Return a Namespace object

    # Convert to dict
    cli_arguments = {key: value for key, value in vars(args).items() if value}

    chain_map = ChainMap(cli_arguments, os.environ, default)
    print(chain_map['username'])

if __name__ == '__main__':
    main()
    os.environ['username'] = 'Hung'
    main()
