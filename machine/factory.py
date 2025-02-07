import ruamel.yaml


def yaml():
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.indent(sequence=3, offset=1)
    return yaml
