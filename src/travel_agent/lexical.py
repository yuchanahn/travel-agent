"""Small Korean lexical tokenizer shared by local evidence indexes."""
import re


def tokens(text):
    """Words plus Korean bigrams; this is not semantic similarity."""
    result = []
    for word in re.findall(r'[a-z0-9]+|[가-힣]+', text.lower()):
        if re.fullmatch('[가-힣]{2,}', word):
            if len(word) > 2:
                result.append(word)
            result.extend('ko:' + word[i:i+2] for i in range(len(word)-1))
        else:
            result.append(word)
    return result
