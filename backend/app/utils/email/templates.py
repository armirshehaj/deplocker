from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("app/templates"), autoescape=select_autoescape()
)


def get_template(template_file_name: str, context_data: dict) -> str:
    template = env.get_template(template_file_name)
    content = template.render(**context_data)

    return content
