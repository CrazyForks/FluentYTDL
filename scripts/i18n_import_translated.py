import sys
import xml.etree.ElementTree as ET
import json
from pathlib import Path

def import_translated(ts_file_path: str, translated_json: str):
    with open(translated_json, 'r', encoding='utf-8') as f:
        translations_dict = json.load(f)
        
    tree = ET.parse(ts_file_path)
    root = tree.getroot()
    
    applied_count = 0
    
    for context in root.findall('context'):
        for message in context.findall('message'):
            source = message.find('source')
            if source is not None and source.text:
                text = source.text
                if text in translations_dict and translations_dict[text]:
                    translation = message.find('translation')
                    if translation is not None:
                        translation.text = translations_dict[text]
                        # 移除 unfinished 标记，表示已翻译完成
                        if 'type' in translation.attrib:
                            del translation.attrib['type']
                        applied_count += 1
                        
    # 将修改后的 XML 写回文件
    tree.write(ts_file_path, encoding='utf-8', xml_declaration=True)
    print(f"Successfully applied {applied_count} translations to {ts_file_path}.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python i18n_import_translated.py <input.ts> <translated.json>")
        sys.exit(1)
        
    import_translated(sys.argv[1], sys.argv[2])
