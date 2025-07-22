import streamlit as st
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.content_understanding_face_client import AzureContentUnderstandingFaceClient
from backend.content_understanding_client import AzureContentUnderstandingClient
import base64
import tempfile
from PIL import Image
import io

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()
# ========== CONFIG ==========
# 请根据实际情况填写
ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
API_VERSION = os.getenv("AZURE_AI_API_VERSION")
SUBSCRIPTION_KEY = os.getenv("AZURE_SUBSCRIPTION_KEY")

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

face_client = AzureContentUnderstandingFaceClient(
    endpoint=ENDPOINT,
    api_version=API_VERSION,
    token_provider=token_provider
)
content_client = AzureContentUnderstandingClient(
    endpoint=ENDPOINT,
    api_version=API_VERSION,
    token_provider=token_provider
)

st.set_page_config(page_title="Face Directory & Video Analyzer", layout="wide")

# ========== SIDEBAR ==========
st.sidebar.title("Operation Manual")
module = st.sidebar.radio(" ", ["Face Management", "Video Analysis"])

# ========== FACE MANAGEMENT ==========
if module == "Face Management":
    st.title("Face Directory Management")
    # 获取所有directory
    directories = face_client.get_person_directories() or []
    if not directories:
        st.warning("No directories found.")
    else:
        # 选择directory
        directory_id = st.selectbox(
            "Select Directory",
            [d.get("personDirectoryId") for d in directories],
            format_func=lambda x: x
        )

        # 获取所有person
        persons = face_client.list_persons(directory_id)
        if not persons:
            persons = []

        person = st.selectbox(
            "Select Person",
            persons,
            format_func=lambda p: p.get("tags", {}).get("name", p.get("personId", ""))
        )
        if person:
            st.subheader(f"Faces of {person.get('tags', {}).get('name', person.get('personId', ''))}")
            faces = face_client.list_faces(directory_id)
            if not faces:
                faces = []
            # 只显示属于该person的face
            faces = [f for f in faces if f.get("personId") == person.get("personId")]
            cols = st.columns(4)
            for idx, face in enumerate(faces):
                with cols[idx % 4]:
                    # 显示图片
                    try:
                        face_data = face_client.get_face(directory_id, face["faceId"])
                        img_bytes = base64.b64decode(face_data["data"])
                        st.image(Image.open(io.BytesIO(img_bytes)), caption=f"Face {face['faceId']}", use_column_width=True)
                    except Exception as e:
                        print(f"Error loading face {face['faceId']}: {e}")
                        st.write(f"Face {face['faceId']}")
                    # 删除按钮
                    if st.button("Delete", key=f"del_{face['faceId']}"):
                        face_client.delete_face(directory_id, face["faceId"])
                        st.success("Face deleted.")
                        st.experimental_rerun()
            st.markdown("---")
            st.subheader("Add New Face")
            uploaded = st.file_uploader("Upload Face Image", type=["jpg", "jpeg", "png"])
            if uploaded and st.button("Add Face"):
                img_bytes = uploaded.read()
                b64 = base64.b64encode(img_bytes).decode()
                face_client.add_face(directory_id, b64, person["personId"])
                st.success("Face added.")
                st.experimental_rerun()

        # ========== 新增功能区块放到底部 ==========
        st.markdown("---")
        with st.expander("➕ Add New Directory"):
            new_dir_id = st.text_input("New Directory ID", key="new_dir_id")
            if st.button("Create Directory", key="create_dir_btn"):
                try:
                    ret = face_client.create_person_directory(new_dir_id)
                    st.success(f"Directory '{new_dir_id}' created.")
                    # Update session state to trigger UI update
                    if "directories" in st.session_state:
                        st.session_state["directories"].append({"personDirectoryId": new_dir_id})
                except Exception as e:
                    st.error(f"Failed to create directory: {e}")

        with st.expander("➕ Add New Person"):
            new_person_name = st.text_input("Person Name", key="new_person_name")
            new_person_tags = st.text_input("Person Tags (optional, JSON format)", value="{}", key="new_person_tags")
            if st.button("Create Person", key="create_person_btn"):
                try:
                    tags = eval(new_person_tags) if new_person_tags.strip() else {}
                    if new_person_name:
                        tags["name"] = new_person_name
                    face_client.add_person(directory_id, tags=tags)
                    st.success(f"Person '{new_person_name}' created.")
                    # Optionally update session state for persons here
                except Exception as e:
                    st.error(f"Failed to create person: {e}")

# ========== VIDEO ANALYSIS ==========
elif module == "Video Analysis":
    st.title("Video Content Analysis")
    st.write("Upload an MP4 video to analyze faces and content.")
    analyzer_id = st.text_input("Analyzer ID", value="your-analyzer-id")
    video_file = st.file_uploader("Upload MP4 Video", type=["mp4"])
    if video_file and st.button("Analyze Video"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_file.read())
            tmp_path = tmp.name
        with st.spinner("Analyzing..."):
            try:
                response = content_client.begin_analyze(analyzer_id, file_location=tmp_path)
                result = content_client.poll_result(response)
                st.subheader("Analysis Result")
                st.json(result)
            finally:
                os.remove(tmp_path)