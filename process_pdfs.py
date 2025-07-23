import json
import pdfplumber
import os
import re
from datetime import datetime

def update_persona_config(path="persona_config.json"):
    print("Update persona configuration:")
    role = input("Enter persona role (e.g., 'Data Scientist'): ")
    expertise = input("Enter persona expertise (e.g., 'Beginner', 'Advanced'): ")
    job = input("Enter job to be done: ")
    keywords = input("Enter keywords (comma separated): ").split(",")
    advanced_terms = input("Enter advanced/technical terms (comma separated, optional): ").split(",")
    config = {
        "persona": {
            "role": role.strip(),
            "expertise": expertise.strip()
        },
        "job": job.strip(),
        "keywords": [k.strip() for k in keywords if k.strip()],
        "advanced_terms": [t.strip() for t in advanced_terms if t.strip()]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"persona_config.json saved with new configuration.")

def read_config(path="persona_config.json"):
    if not os.path.exists(path):
        print(f"{path} not found. Please update persona config first.")
        exit(1)
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    persona = d.get('persona', {})
    job = d.get('job', '')
    keywords = d.get('keywords', [])
    advanced_terms = d.get('advanced_terms', [])
    return persona, job, keywords, advanced_terms

def extract_lines_from_pdf(pdf_path):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            for obj in page.extract_words(extra_attrs=['size', 'fontname', 'x0', 'top']):
                lines.append({
                    'text': obj['text'],
                    'size': obj['size'],
                    'fontname': obj['fontname'],
                    'x0': obj['x0'],
                    'top': obj['top'],
                    'page': page_num
                })
    return lines

def detect_section_headers(lines):
    if not lines:
        return
    largest_size = max(line['size'] for line in lines)
    for idx, line in enumerate(lines):
        text = line['text'].strip()
        if line['size'] == largest_size and line['page'] == 1:
            yield idx, {'level': 'Title', 'title': text, 'page': line['page']}
        elif re.match(r'^\d+\.\d+\.\d+', text):
            yield idx, {'level': 'H3', 'title': text, 'page': line['page']}
        elif re.match(r'^\d+\.\d+', text):
            yield idx, {'level': 'H2', 'title': text, 'page': line['page']}
        elif re.match(r'^\d+\.', text):
            yield idx, {'level': 'H1', 'title': text, 'page': line['page']}
        elif text.isupper() and line['size'] >= largest_size - 1.5 and len(text) > 3:
            yield idx, {'level': 'H1', 'title': text, 'page': line['page']}

def extract_sections(lines):
    headers = list(detect_section_headers(lines))
    sections = []
    for i, (idx, header) in enumerate(headers):
        start = idx + 1
        end = headers[i+1][0] if i+1 < len(headers) else len(lines)
        section_content = "\n".join(lines[j]['text'] for j in range(start, end))
        d = {
            "title": header["title"],
            "level": header["level"],
            "page": header["page"],
            "content": section_content
        }
        sections.append(d)
    return sections

def score_section(sec, keywords, persona_expertise=None, advanced_terms=None):
    text = f"{sec.get('title', '')} {sec.get('content','')}".lower()
    kw_score = sum(1 for kw in keywords if kw.lower() in text)
    adv_score = 0
    if persona_expertise and 'advanced' in persona_expertise.lower() and advanced_terms:
        adv_score = sum(1 for term in advanced_terms if term in text)
    return kw_score + adv_score

def extract_top_snippet(content, keywords):
    paras = content.split('\n')
    scores = [(p, sum(1 for k in keywords if k.lower() in p.lower())) for p in paras]
    scores = [t for t in scores if t[1] > 0]
    if scores:
        return max(scores, key=lambda t: t[1])[0]
    return ""

def main(persona, job, keywords, advanced_terms):
    input_folder = './input_pdfs'
    output_folder = './output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    all_sections = []
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print(f"No PDFs found in {input_folder}. Please add PDFs and try again.")
        return

    for filename in pdf_files:
        pdf_path = os.path.join(input_folder, filename)
        print(f"Processing {filename}...")
        lines = extract_lines_from_pdf(pdf_path)
        sections = extract_sections(lines)
        for sec in sections:
            sec['document'] = filename
            all_sections.append(sec)

    # Score and rank
    for sec in all_sections:
        sec['score'] = score_section(
            sec, keywords,
            persona_expertise=persona.get('expertise',''),
            advanced_terms=advanced_terms
        )

    # Filter and rank by score
    ranked_sections = sorted([s for s in all_sections if s['score'] > 0], key=lambda x: x['score'], reverse=True)

    # Prepare output JSON
    output = {
        "metadata": {
            "persona": persona,
            "job": job,
            "timestamp": str(datetime.now()),
            "pdfs": sorted(list(set(sec["document"] for sec in ranked_sections)))
        },
        "results": []
    }
    for i, sec in enumerate(ranked_sections, 1):
        output["results"].append({
            "document": sec["document"],
            "page": sec["page"],
            "section_title": sec["title"],
            "section_level": sec["level"],
            "relevance_rank": i,
            "relevance_score": sec["score"],
            "snippet": extract_top_snippet(sec['content'], keywords)
        })

    output_path = os.path.join(output_folder, "persona_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Done! Results saved to {output_path}")

if __name__ == "__main__":
    update = input("Do you want to update persona_config.json? (y/n): ").strip().lower()
    if update == "y":
        update_persona_config()
    persona, job, keywords, advanced_terms = read_config()
    main(persona, job, keywords, advanced_terms)
