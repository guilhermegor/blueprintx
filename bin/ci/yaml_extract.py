import pathlib
import sys

import yaml


PROSE_KEYS = ("name", "description")


class TolerantLoader(yaml.SafeLoader):
    pass


def _ignore_tag(loader, str_suffix, node):
    return None


TolerantLoader.add_multi_constructor("", _ignore_tag)


def load(path_file):
    return yaml.load(pathlib.Path(path_file).read_text(encoding="utf-8"), Loader=TolerantLoader)


def nav_pages(node):
    if isinstance(node, str):
        is_page = node.endswith(".md") and not node.startswith(("http://", "https://"))
        return [node] if is_page else []
    if isinstance(node, dict):
        return [str_page for value in node.values() for str_page in nav_pages(value)]
    if isinstance(node, list):
        return [str_page for item in node for str_page in nav_pages(item)]
    return []


def scalars(node):
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [
            str_text
            for key, value in node.items()
            if key not in PROSE_KEYS or not isinstance(value, str)
            for str_text in scalars(value)
        ]
    if isinstance(node, list):
        return [str_text for item in node for str_text in scalars(item)]
    return []


def main(list_args):
    str_mode, path_file = list_args
    doc = load(path_file)
    if str_mode == "nav":
        doc = doc.get("nav") if isinstance(doc, dict) else None
        list_out = nav_pages(doc)
    else:
        list_out = scalars(doc)
    if str_mode == "nav":
        list_out = sorted(set(list_out))
    for str_line in list_out:
        print(str_line)


if __name__ == "__main__":
    main(sys.argv[1:])
