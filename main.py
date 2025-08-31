import sys

from code_review.ai_review import code_review_main

scripts = [
    'ai_review'
]

def main():
    args = sys.argv[1:]
    if len(args) == 0:
        print("No script specified! Please specify one as an argument.")
        print(f"Options: {scripts}")
        return -1

    script = args[0]
    if (script == 'ai_review'):
        code_review_main()
    else:
        print(f"{script} is not a valid script option.\n")
        print(f"Options: {', '.join(scripts)}")
        return -1

if __name__ == "__main__":
    main()