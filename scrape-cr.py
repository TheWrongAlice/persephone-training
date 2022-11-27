import csv
import re
import requests
from bs4 import BeautifulSoup
import json

PROMPT_SEPARATOR = "###" #\n###\n\n"
COMPLETION_PREFIX = ' '
COMPLETION_STOP_SEQUENCE = "\n"
MAX_TOKENS = 2048
ASSUMED_CHARS_PER_TOKEN = 3
prompts = []

def clean_transcript(dirty):
    def h2search(query):
        return re.search(f"<h2>.*{query}.*</h2>", dirty, flags=re.IGNORECASE)
    def h2split(delimiter, text):
        return re.split(f"<h2>.*{delimiter}.*</h2>", text, flags=re.IGNORECASE)
    def remove_links(text):
        return re.sub('<a[^<]+?>', '', text).replace('</a>', '')

    # We assume a certain document structure. If the text does not match our assumptions, we will not clean it.
    if bool(h2search('Pre-Show') and h2search('Part I') and h2search('Break') and h2search('Part II')):
        # Do magic
        part1 = h2split('Break', h2split('Part I', dirty)[1])[0]
        part2 = h2split('Part II', dirty)[1]
        return remove_links(part1 + part2)

    # Log a warning since this is not ideal
    print ('WARNING: Transcript was not cleaned because it did not match the assumed structure.')
    return remove_links(dirty)

def import_transcript_from_url(url):
    html_doc = requests.get(url)
    soup = BeautifulSoup(html_doc.text, 'html.parser')
    ts_wrapper = soup.find('div', class_='mw-parser-output')
    transcript = clean_transcript(str(ts_wrapper))
    paragraphs = BeautifulSoup(transcript, 'html.parser').find_all('p')
    return paragraphs

def clean_paragraph(p):
    p_text = str(p)
    p_text = p_text.replace('<p>', '').replace('</p>', '')
    p_text = p_text.replace('“', '"').replace('”', '"')
    p_text = p_text.replace(f"{dm_name}:", f"{dm_name} (Dungeon Master):")
    return p_text.strip()

workdir = 'critical role transcripts'
with open('cr_transcript_links.csv') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    line_count = 0
    for row in csv_reader: # Each instance of this loop generates a prompt/completion pair
        if line_count == 0:
            line_count += 1
        else:
            transcript_name = re.sub('[^A-Za-z0-9 ]+', '', f"{row[0]} {row[1].replace('D&', 'Dn').replace('&', 'and')}").replace('  ', ' ')
            transcript_url = row[3]
            dm_name = row[2]
            print(f'{dm_name}: {transcript_name}: {transcript_url}')
            line_count += 1

            paragraphs = import_transcript_from_url(transcript_url)
            for index in range(len(paragraphs)-1,0,-1): # Reverse loop
                print(f"index {index}")
                if index == 0:
                    continue

                print(f"Starting new completion/prompt at: {index}")
                completion = clean_paragraph(paragraphs[index])

                # Built a prompt/completion pair using this paragraph as the completion, and
                # previous paragraphs as the prompt.
                prompt = ''

                # Ensure that the prompt + completion doesn't exceed 2048 tokens, including the separator.
                for steps in range(1,1000):
                    print(f"steps {steps}")
                    print(f"filling prompt from paragraph {index-steps}")
                    previous_index = index-steps
                    if previous_index < 0:
                        print('derp')
                        break
                    previous = clean_paragraph(paragraphs[index-steps])
                    test = len(f"{previous}\n{prompt}{PROMPT_SEPARATOR}{completion}{COMPLETION_STOP_SEQUENCE}") / ASSUMED_CHARS_PER_TOKEN > MAX_TOKENS

                    if test:
                        break
                    else:
                        if prompt:
                            prompt = f"{previous}\n{prompt}"
                        else:
                            prompt = previous

                prompts.append({
                    'prompt': prompt + PROMPT_SEPARATOR,
                    'completion': COMPLETION_PREFIX + completion + COMPLETION_STOP_SEQUENCE
                })
                #print(f"PROMPT: {prompt_with_context}")
                #print(f"COMPLE: {completion}")
                #print(f"LENGTH: {len(prompt+PROMPT_SEPARATOR+completion)}")
                #break # After the first prompt
            #print(prompts)

            f = open("demofile2.jsonl", "a")
            for prompt in prompts:
                f.write(f"{json.dumps(prompt)}\n")
            f.close()

            exit() # After the first transcript

    print(f'Processed {line_count} lines.')
