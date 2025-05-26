import os
import openai


openai.api_key = "sk-CE51TbLXwnFgXtoX17A1C59e31274aA29062E7E47b800d57"

# all client options can be configured just like the `OpenAI` instantiation counterpart
openai.base_url = "https://free.v36.cm/v1/"
openai.default_headers = {"x-foo": "true"}

completion = openai.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "user",
            "content": "Why is the api so slow",
        },
    ],
)
print(completion.choices[0].message.content)

# 正常会输出结果：Hello there! How can I assist you today ?