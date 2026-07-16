import json
import sys
import xml.etree.ElementTree as ET


def export_untranslated(ts_file_path: str, output_json: str):
    tree = ET.parse(ts_file_path)
    root = tree.getroot()
    untranslated_count = 0
    
    translations_dict = {}
    
    for context in root.findall('context'):
        for message in context.findall('message'):
            translation = message.find('translation')
            # 找到 type="unfinished" 或者 内容为空 的 translation
            if translation is not None and (translation.get('type') == 'unfinished' or not translation.text):
                source = message.find('source')
                if source is not None and source.text:
                    text = source.text
                    if text not in translations_dict:
                        translations_dict[text] = ""
                        untranslated_count += 1
                        
    # 将字典保存为 JSON，方便查阅和发送给 AI
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(translations_dict, f, ensure_ascii=False, indent=4)
        
    print(f"Exported {untranslated_count} untranslated strings to {output_json}.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python i18n_export_untranslated.py <input.ts> <output.json>")
        sys.exit(1)
        
    export_untranslated(sys.argv[1], sys.argv[2])
