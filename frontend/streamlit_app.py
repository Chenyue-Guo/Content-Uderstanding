import streamlit as st
import os
import sys
import base64
import tempfile
import io

from PIL import Image
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# 尝试导入 OpenCV，用于本地抽帧兜底（未安装也不影响云端抽帧）
try:
    import cv2
except ImportError:
    cv2 = None

# ===== 将项目根目录加入 PYTHONPATH （保持你原来的逻辑） =====
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.content_understanding_face_client import AzureContentUnderstandingFaceClient
from backend.content_understanding_client import AzureContentUnderstandingClient

load_dotenv()

# ========== CONFIG ==========
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

# -----------------------------------
# 辅助函数
# -----------------------------------
def ms_to_ts(ms: int) -> str:
    """毫秒 → 00:00.000 格式字符串"""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    return f"{m:02d}:{s:02d}.{ms:03d}"

def pick_key_time(start: int, end: int, key_times: list[int]) -> int:
    """取区间内最靠近 start 的关键帧；若该段没有关键帧，则返回区间中点"""
    in_seg = [t for t in key_times if start <= t <= end]
    return in_seg[0] if in_seg else (start + end) // 2

def fetch_frame(operation_id: str, tmp_video_path: str, time_ms: int) -> bytes | None:
    """
    先尝试 Azure Content Understanding 的 get_frame API，
    若不可用或失败，再用本地 OpenCV 从视频抽帧。
    返回 JPG bytes；若两种方式都失败则返回 None。
    """
    # ---- 1️⃣ Azure API 抽帧 ----
    try:
        data = content_client.get_frame(operation_id=operation_id, time_ms=time_ms)
        if isinstance(data, dict) and "data" in data:
            print("Fetched frame from Azure API")
            return base64.b64decode(data["data"])
    except Exception:
        pass  # 转而尝试本地

    # ---- 2️⃣ OpenCV 本地抽帧 ----
    if cv2 is None:
        return None
    try:
        cap = cv2.VideoCapture(tmp_video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, time_ms)
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            _, buf = cv2.imencode(".jpg", frame)
            print("Fetched frame from local OpenCV")
            return buf.tobytes()
    except Exception:
        pass
    return None

# ========== FACE MANAGEMENT ==========
if module == "Face Management":
    st.title("Face Directory Management")

    directories = face_client.get_person_directories() or []
    if not directories:
        st.warning("No directories found.")
    else:
        directory_id = st.selectbox(
            "Select Directory",
            [d.get("personDirectoryId") for d in directories],
            format_func=lambda x: x
        )

        persons = face_client.list_persons(directory_id) or []
        person = st.selectbox(
            "Select Person",
            persons,
            format_func=lambda p: p.get("tags", {}).get("name", p.get("personId", ""))
        )

        if person:
            st.subheader(f"Faces of {person.get('tags', {}).get('name', person.get('personId', ''))}")
            faces = face_client.list_faces(directory_id) or []
            faces = [f for f in faces if f.get("personId") == person.get("personId")]
            cols = st.columns(4)
            for idx, face in enumerate(faces):
                with cols[idx % 4]:
                    try:
                        face_data = face_client.get_face(directory_id, face["faceId"])
                        img_bytes = base64.b64decode(face_data["data"])
                        st.image(Image.open(io.BytesIO(img_bytes)), caption=f"Face {face['faceId']}", use_container_width=True)
                    except Exception as e:
                        st.write(f"Face {face['faceId']} (load error: {e})")
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

        # ---- 新增目录 & 新增人员 ----
        st.markdown("---")
        with st.expander("➕ Add New Directory"):
            new_dir_id = st.text_input("New Directory ID", key="new_dir_id")
            if st.button("Create Directory", key="create_dir_btn"):
                try:
                    face_client.create_person_directory(new_dir_id)
                    st.success(f"Directory '{new_dir_id}' created.")
                except Exception as e:
                    st.error(f"Failed to create directory: {e}")

        with st.expander("➕ Add New Person"):
            new_person_name = st.text_input("Person Name", key="new_person_name")
            new_person_tags = st.text_input("Person Tags (optional, JSON)", value="{}", key="new_person_tags")
            if st.button("Create Person", key="create_person_btn"):
                try:
                    tags = eval(new_person_tags) if new_person_tags.strip() else {}
                    if new_person_name:
                        tags["name"] = new_person_name
                    face_client.add_person(directory_id, tags=tags)
                    st.success(f"Person '{new_person_name}' created.")
                except Exception as e:
                    st.error(f"Failed to create person: {e}")

# ========== VIDEO ANALYSIS ==========
elif module == "Video Analysis":
    st.title("Video Content Analysis")
    st.write("Upload an MP4 video to analyze faces and content.")
    analyzer_id = st.text_input("Analyzer ID", value="prebuilt-videoAnalyzer")
    video_file = st.file_uploader("Upload MP4 Video", type=["mp4"])

    if video_file and st.button("Analyze Video"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_file.read())
            tmp_path = tmp.name

        with st.spinner("Analyzing..."):
            try:
                # 调用 Azure 预构建分析器
                resp = content_client.begin_analyze(analyzer_id, file_location=tmp_path)
                result = content_client.poll_result(resp)

                # 显示原始 JSON
                with st.expander("🔍 Raw JSON"):
                    st.json(result)

                # 解析段落与关键帧
                inner = result.get("contents") or result.get("result", {}).get("contents")
                if not inner:
                    st.error("无法在返回结果中找到 contents")
                    st.stop()
                contents = inner[0]

                segments = contents.get("segments", [])
                key_times = contents.get("KeyFrameTimesMs", [])

                st.subheader("Segments with Key Frames")
                for seg in segments:
                    start_ms, end_ms = seg["startTimeMs"], seg["endTimeMs"]
                    seg_id = seg.get("segmentId", "?")
                    desc = seg.get("description", "")
                    frame_ms = pick_key_time(start_ms, end_ms, key_times)
                    img_bytes = fetch_frame(result["id"], tmp_path, frame_ms)

                    # ---- UI：左文字右图片 ----
                    col1, col2 = st.columns([2, 3])
                    with col1:
                        st.markdown(f"#### Segment {seg_id}  \n{ms_to_ts(start_ms)} — {ms_to_ts(end_ms)}")
                        st.write(desc)
                    with col2:
                        if img_bytes:
                            st.image(img_bytes, caption=ms_to_ts(frame_ms), use_container_width=True)
                        else:
                            st.info("无法获取关键帧")
                    st.markdown("---")
            finally:
                os.remove(tmp_path)