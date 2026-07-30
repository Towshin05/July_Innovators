
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


import streamlit as st


from database.db import init_db, get_session
from database.models import Evidence, Incident, Brief
from services.evidence_processor import process_evidence
from services.report_service import generate_pdf


st.set_page_config(
    page_title="WitnessBridge AI",
    page_icon="📰",                
    layout="wide",
    initial_sidebar_state="expanded",
)


init_db()


def _init_state(key: str, default):

    if key not in st.session_state:
        st.session_state[key] = default

_init_state("last_result", None)            
_init_state("selected_incident_id", None)   
_init_state("last_pdf_path", None)           
_init_state("filter_category", "All")        



def page_upload():
    """Render the upload page.

    Layout:
        - Hero header with the project name and tagline.
        - File uploader (image/* or application/pdf).
        - On submit: spinner, calls process_evidence(), shows the result.
        - Three info cards: headline, summary, key facts.
    """
  
    st.title("📰WitnessBridge AI")
    st.markdown(
        "**Citizen Evidence Intelligence Platform**  \n"
        "Upload images or PDFs of citizen evidence. "
        "Get a structured media brief in seconds."
    )

   

  
    with st.expander("ℹ️ What this app does", expanded=False):
        st.markdown(
            """
            1. **OCR** extracts text from images (Bangla + English).
            2. **PDF parsing** pulls text from PDFs (with OCR fallback for scans).
            3. **Gemma** analyzes the text and produces a structured brief.
            4. **SQLite** persists the analysis for later review.
            5. **ReportLab** generates a downloadable PDF press brief.

            The platform **does not verify** evidence. It structures
            it for journalists, NGOs, and humanitarian organizations.
            """
        )

   
    uploaded = st.file_uploader(
        "Choose an evidence file",
        type=["png", "jpg", "jpeg", "pdf"],
        accept_multiple_files=False,
        help="PNG, JPG, or PDF. Max 200MB.",
    )

    if uploaded is None:
        st.info("Upload a file to begin.")
        return

    file_size_kb = uploaded.size / 1024
    st.success(f"📎 **{uploaded.name}** ({file_size_kb:.1f} KB)")


    ext = Path(uploaded.name).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
    }
    mime_type = mime_map.get(ext)
    if not mime_type:
      
        st.error(f"Unsupported file type: {ext}")
        return

 
    if st.button("🔍 Analyze Evidence", type="primary", use_container_width=True):
     
        with st.spinner("Processing evidence... (this may take 20-60 seconds)"):
          
         
            temp_path = Path("uploads") / f"_temp_{uploaded.name}"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(uploaded.getbuffer())

            try:
               
                result = process_evidence(str(temp_path), mime_type)
                st.session_state["last_result"] = result
            except FileNotFoundError as e:
                st.error(f"❌ File error: {e}")
                return
            except RuntimeError as e:
              
                st.error(f"❌ Processing failed: {e}")
                return
            except ValueError as e:
              
                st.error(f"❌ {e}")
                return
            except Exception as e:
     
                st.error(f"❌ Unexpected error: {e}")
                return
            finally:
           
                temp_path.unlink(missing_ok=True)

       
        if result.get("deduplicated"):
            st.warning("⚠️ This file was uploaded before. Showing the existing analysis.")
        else:
            st.success("✅ Analysis complete. View details below or on the **Detail** page.")

        st.divider()
        st.subheader(" Quick Preview")

     
        col1, col2, col3 = st.columns(3)
        col1.metric("Category", result["category"] or "—")
        col2.metric("Location", result["location"] or "—")
        col3.metric("Date", result["occurred_at"] or "unclear")

       
        st.markdown(
            f"###  {result['headline']}"
        )

      
        st.markdown(f"**Summary:** {result['summary']}")

       
        if result.get("visual_description"):
            st.markdown(f"**Visual Description:** {result['visual_description']}")

        if result["key_facts"]:
            st.markdown("**Key Facts:**")
            for fact in result["key_facts"]:
                st.markdown(f"- {fact}")

      
        if st.button("📄 Open Full Detail Page", use_container_width=True):
            st.session_state["selected_incident_id"] = result["incident_id"]
            st.page_link(detail_page, label="Go to Detail", icon="📄")



def page_dashboard():
  
    st.title("📊 Incident Dashboard")
    st.markdown("All incidents processed by WitnessBridge AI.")


    with get_session() as session:
     
        rows = session.query(Incident.category).distinct().all()
       
        categories = sorted([r[0] for r in rows if r[0]])

    filter_options = ["All"] + categories
    selected = st.selectbox(
        "Filter by category",
        filter_options,
        index=filter_options.index(st.session_state["filter_category"])
            if st.session_state["filter_category"] in filter_options else 0,
    )
    
    st.session_state["filter_category"] = selected

   
    with get_session() as session:
        q = session.query(Incident).join(Evidence)
       
        if selected != "All":
            q = q.filter(Incident.category == selected)

   
        incidents = q.order_by(Incident.created_at.desc()).all()

        if not incidents:
            st.info("No incidents yet. Upload one on the **Upload** page.")
            return

   
        rows = []
        for inc in incidents:
            rows.append({
                "ID": inc.id,
                "Date Added": inc.created_at.strftime("%Y-%m-%d %H:%M"),
                "Category": inc.category,
                "Location": inc.location or "—",
                "Occurred": inc.occurred_at.strftime("%Y-%m-%d") if inc.occurred_at else "unclear",
                "Headline": inc.brief.headline if inc.brief else "(no brief)",
                "Evidence": inc.evidence.filename,
            })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Headline": st.column_config.TextColumn("Headline", width="large"),
        },
    )

    st.divider()
    st.subheader("Open an Incident")

    options = {
        inc.id: f"#{inc.id} — {inc.brief.headline if inc.brief else '(no brief)'}"
        for inc in incidents
    }


    default_index = 0
    if st.session_state["selected_incident_id"] in options:
        default_index = list(options.keys()).index(st.session_state["selected_incident_id"])

    chosen_id = st.selectbox(
        "Incident",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=default_index,
    )

    if st.button("📄 View Detail", type="primary"):
        st.session_state["selected_incident_id"] = chosen_id
       
        st.page_link(detail_page, label="Open Detail", icon="📄")


def page_detail():

    st.title("📄 Incident Detail")


    incident_id = st.session_state.get("selected_incident_id")
    if not incident_id:
        st.info("👈 Pick an incident from the dashboard first.")
      
        st.page_link(dashboard_page, label="Go to Dashboard", icon="📊")
        return


    with get_session() as session:
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            st.error(f"No incident with id={incident_id}")
            return

  
        brief = incident.brief
        evidence = incident.evidence

        headline = brief.headline if brief else "(no brief)"
        body_md = brief.body_markdown if brief else ""
        category = incident.category
        location = incident.location or "unclear"
        summary = incident.summary
        occurred_at_str = (
            incident.occurred_at.strftime("%d %B %Y")
            if incident.occurred_at
            else "Date unclear"
        )

        try:
            key_facts = json.loads(incident.key_facts or "[]")
            if not isinstance(key_facts, list):
                key_facts = []
        except (json.JSONDecodeError, TypeError, ValueError):
            key_facts = []

        visual_description = incident.visual_description or ""

       
        existing_pdf = brief.pdf_path if brief else None

    st.page_link(dashboard_page, label="← Back to Dashboard", icon="📊")

    st.markdown(f"# 📰 {headline}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Category", category)
    col2.metric("Location", location)
    col3.metric("Date", occurred_at_str)

    st.divider()

   
    st.subheader("Summary")
    st.write(summary)

    
    if visual_description and visual_description.strip() and \
            visual_description.strip().lower() != "no image provided":
        st.subheader("Visual Description")
        st.write(visual_description)

    # KEY FACTS.
    if key_facts:
        st.subheader("Key Facts")
        for fact in key_facts:
            st.markdown(f"- {fact}")

 
    st.subheader("Full Brief")
    if body_md:
        st.markdown(body_md)
    else:
        st.info("No body text available.")

    
    if evidence:
        st.divider()
        st.subheader("Source Evidence")
      
        if evidence.mime_type and evidence.mime_type.startswith("image/"):
            stored = Path(evidence.stored_path)
            if stored.exists():
                st.image(str(stored), caption=f"Uploaded: {evidence.filename}",
                         use_container_width=True)
        st.markdown(f"- **Filename:** `{evidence.filename}`")
        st.markdown(f"- **Type:** `{evidence.mime_type}`")
        st.markdown(f"- **Stored at:** `{evidence.stored_path}`")
        st.markdown(f"- **Uploaded:** {evidence.created_at.strftime('%Y-%m-%d %H:%M')}")
       
        if evidence.extracted_text:
            with st.expander("📜 View extracted text (raw OCR/PDF output)"):
                st.text(evidence.extracted_text[:2000] + ("..." if len(evidence.extracted_text) > 2000 else ""))

    st.divider()
    st.subheader("📥 Export")

  
    if existing_pdf and Path(existing_pdf).exists():
        st.success(f"PDF already generated: `{existing_pdf}`")
        with open(existing_pdf, "rb") as f:
           
            st.download_button(
                label="⬇️ Download PDF",
                data=f.read(),
                file_name=f"incident_{incident_id}_brief.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )

    if st.button("🔄 Generate PDF", use_container_width=True):
        with st.spinner("Generating PDF..."):
            try:
                pdf_path = generate_pdf(incident_id)
                st.session_state["last_pdf_path"] = str(pdf_path)
                st.success(f"✅ PDF generated: `{pdf_path}`")
           
                st.rerun()
            except Exception as e:
                st.error(f"❌ PDF generation failed: {e}")



def page_about():
    """Render the about page with project info, ethics, and run instructions."""
    st.title("ℹ️ About WitnessBridge AI")

    st.markdown(
        """
        ## What it is

        WitnessBridge AI is an evidence intelligence platform for journalists,
        NGOs, and humanitarian organizations. It collects citizen-submitted
        evidence (photos, scanned documents, PDFs) and turns it into structured
        media briefs.

        ## How it works

        1. **Upload** an image or PDF of citizen evidence.
        2. **OCR** (EasyOCR) extracts text — handles Bangla and English.
        3. **Gemma 2 9B** (via Hugging Face) analyzes the text and produces
           a structured JSON output (category, location, facts, summary).
        4. **SQLite** stores the incident for later review.
        5. **ReportLab** renders a downloadable A4 PDF brief.

        ## What it does NOT do

        - It does **not** verify evidence.
        - It does **not** authenticate sources.
        - It does **not** assign blame or speculate beyond the source text.
        - It does **not** store evidence off your machine.

        All data lives in `database/witnessbridge.db` on your local disk.
        Uploaded files live in `uploads/`. Generated PDFs live in `reports/`.

    
        ## Future work

        - Audio/video transcription via Whisper
        - Multi-language UI (Bengali interface)
        - Authentication and audit logging
        - Cloud deployment with object storage
        """
    )



upload_page = st.Page(
    page_upload,
    title="Upload Evidence",
    icon="📤",
    default=True,  
)

dashboard_page = st.Page(
    page_dashboard,
    title="Dashboard",
    icon="📊",
)

detail_page = st.Page(
    page_detail,
    title="Detail",
    icon="📄",
)

about_page = st.Page(
    page_about,
    title="About",
    icon="ℹ️",
)


nav = st.navigation([upload_page, dashboard_page, detail_page, about_page])

nav.run()


