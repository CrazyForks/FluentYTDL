import re

with open('src/fluentytdl/ui/help_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'QT_TRANSLATE_NOOP' not in content:
    content = content.replace('from PySide6.QtCore import Qt, Signal', 'from PySide6.QtCore import Qt, Signal, QT_TRANSLATE_NOOP, QCoreApplication')

pattern = re.compile(r'^(_[A-Z0-9_]+_HTML) = \"\"\"(.*?)\"\"\"', re.DOTALL | re.MULTILINE)

def repl(m):
    var_name = m.group(1)
    inner = m.group(2)
    if 'QT_TRANSLATE_NOOP' in inner:
        return m.group(0)
    return f'{var_name} = QT_TRANSLATE_NOOP("HelpWindow", """{inner}""")'

new_content = pattern.sub(repl, content)

with open('src/fluentytdl/ui/help_window.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done wrapping constants.')
