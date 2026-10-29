
import os
import json
from dotenv import load_dotenv
from groq import Groq
from src.LLM.category_select import get_top_categories
from src.LLM.TEMPLATES.main_template import PROMPT_TEMPLATE
from src.LLM.TEMPLATES.min_attribute import PROMPT_TEMPLATE_ATT_MIN

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Models list for further changing 
# models = client.models.list()
# for model in models.data:
#     print(model.id)


def attributes(template,promt_main):
    att_template={}
    att_template["user_promt"]=promt_main 
    att_template["items"]=[]
    for i,values in enumerate(template['items']):
        att_template["items"].append({})
        att_template["items"][i]['name']=values['name']
        att_template["items"][i]['preferences']=values['preferences']

    prompt =  PROMPT_TEMPLATE_ATT_MIN.replace(
        "{input_json}",
        json.dumps(att_template, ensure_ascii=False)
    )
    response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "Extract attributes accurately. Return JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
    )
    att_template=json.loads(response.choices[0].message.content)# pyright: ignore[reportArgumentType]
    for i,values in enumerate(template['items']):
        template["items"][i]['attributes']=att_template["items"][i]['attributes']
    return template

   
    
def adding_category(template):
    llm_items=template["items"]
    for i in range(len(llm_items)):
        llm_category=template["items"][i]["name"]
        results,category_ids=get_top_categories(llm_category)
        print(results)
        template["items"][i]["category_id"]=category_ids 
    return template

def extract_requirements(user_prompt):
    prompt = PROMPT_TEMPLATE.replace("{user_prompt}", user_prompt)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "Extract requirements accurately. Return JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    template=json.loads(response.choices[0].message.content)# pyright: ignore[reportArgumentType]
    template=attributes(template,user_prompt)
    main_template=adding_category(template)

    
    return main_template




