import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--global_root_dir')
    parser.add_argument('--global_results_dir_name')
    parser.add_argument('--prefix')

    return parser.parse_args()
