from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter

loader = TextLoader("mps_knowledge.txt", encoding="utf-8")
documents = loader.load()

text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = text_splitter.split_documents(documents)

embedding_model = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")

vector_db = Chroma.from_documents(docs, embedding_model, persist_directory="./chroma_db")
print("지식 베이스 구축 완료!")
