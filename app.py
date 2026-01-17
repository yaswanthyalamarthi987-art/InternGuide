from flask import Flask, render_template, request, redirect, session, send_file, jsonify
import os, re, sqlite3
import PyPDF2
from collections import Counter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ================= APP SETUP =================
app = Flask(__name__)
app.secret_key = "internguide_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    return conn

# ================= DATA =================
SKILLS = [
    "Python","Java","C++","HTML","CSS","JavaScript",
    "Flask","Django","SQL","Git",
    "Data Analysis","Machine Learning"
]

INTERNSHIPS = {
    "Web Developer Intern":["HTML","CSS","JavaScript","Flask","Git"],
    "Python Developer Intern":["Python","Flask","Git"],
    "Data Analyst Intern":["Python","SQL","Data Analysis"]
}

LEARNING_RESOURCES = {
    "Git":[("Git & GitHub for Beginners","https://www.youtube.com/watch?v=RGOj5yH7evk")],
    "SQL":[("SQL Full Course","https://www.youtube.com/watch?v=HXV3zeQKqGY")],
    "Flask":[("Flask Tutorial","https://www.youtube.com/watch?v=Z1RJmh_OqeA")]
}

# ================= HELPERS =================
def extract_text(path):
    reader = PyPDF2.PdfReader(open(path,"rb"))
    text = ""
    for p in reader.pages:
        text += p.extract_text() or ""
    return text.lower()

def detect_skills(text):
    return [s for s in SKILLS if re.search(rf"\b{s.lower()}\b", text)]

def resume_score(skills):
    return min(100, len(skills) * 8)

def ats_score(skills):
    required = set(sum(INTERNSHIPS.values(), []))
    return int(len(set(skills) & required) / len(required) * 100) if required else 0

def login_required():
    return "user" in session

# ================= AUTH =================
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        db = get_db()
        try:
            db.execute("INSERT INTO users(username,password) VALUES(?,?)", (u, p))
            db.commit()
            return redirect("/login")
        except:
            return render_template("signup.html", error="Username already exists")
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        db = get_db()
        cur = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?", (u, p)
        )
        if cur.fetchone():
            session["user"] = u
            return redirect("/")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= PAGES =================
@app.route("/")
def home():
    if not login_required():
        return redirect("/login")
    return render_template("home.html")

@app.route("/upload", methods=["GET","POST"])
def upload():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        file = request.files["resume"]
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(path)

        text = extract_text(path)
        skills = detect_skills(text)

        score = resume_score(skills)
        ats = ats_score(skills)

        strengths, weaknesses, suggestions = [], [], []

        if skills:
            strengths.append(
                "The resume demonstrates proficiency in the following technical skills: "
                + ", ".join(skills) + "."
            )

        if ats < 60:
            weaknesses.append("Low ATS keyword relevance detected.")
            suggestions.append(
                "Add more role-specific keywords to improve ATS compatibility."
            )

        if "Git" not in skills:
            weaknesses.append("Version control using Git is not mentioned.")
            suggestions.append("Consider learning Git and adding it to your resume.")

        suggestions.append("Include at least one relevant project.")

        recommendations, missing = [], []
        for role, req in INTERNSHIPS.items():
            matched = [s for s in req if s in skills]
            match = int(len(matched) / len(req) * 100)
            recommendations.append({"role": role, "match": match})
            missing.extend([r for r in req if r not in skills])

        checklist = [
            "Add role-specific keywords.",
            "Ensure ATS-friendly formatting.",
            "Limit resume to one or two pages.",
            "Include relevant projects."
        ]

        resources = {k: LEARNING_RESOURCES[k] for k in set(missing) if k in LEARNING_RESOURCES}

        # PDF report
        pdf_path = "uploads/InternGuide_Report.pdf"
        doc = SimpleDocTemplate(pdf_path)
        styles = getSampleStyleSheet()
        doc.build([
            Paragraph("InternGuide Resume Analysis Report", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Resume Score: {score}/100", styles["Normal"]),
            Paragraph(f"ATS Keyword Score: {ats}/100", styles["Normal"])
        ])

        return render_template(
            "result.html",
            resume_score=score,
            ats_score=ats,
            skills=skills,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            recommendations=recommendations,
            checklist=checklist,
            resources=resources
        )

    return render_template("upload.html")

# ================= RESUME MAKER (FORM → PDF) =================
@app.route("/resume-maker", methods=["GET","POST"])
def resume_maker():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        d = request.form
        pdf_path = "uploads/Generated_Resume.pdf"
        doc = SimpleDocTemplate(pdf_path)
        styles = getSampleStyleSheet()
        content = [
            Paragraph(f"<b>{d['name']}</b>", styles["Title"]),
            Paragraph(d["email"], styles["Normal"]),
            Spacer(1, 12),
            Paragraph("<b>Technical Skills</b>", styles["Heading2"]),
            Paragraph(d["skills"], styles["Normal"]),
            Paragraph("<b>Experience</b>", styles["Heading2"]),
            Paragraph(d["experience"], styles["Normal"])
        ]
        doc.build(content)
        return send_file(pdf_path, as_attachment=True)

    return render_template("resume_maker.html")

# ================= API RESUME BUILDER =================
@app.route("/api/build-resume", methods=["POST"])
def api_build_resume():
    data = request.json

    pdf_path = "uploads/API_Generated_Resume.pdf"
    doc = SimpleDocTemplate(pdf_path)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph(f"<b>{data['name']}</b>", styles["Title"]))
    content.append(Paragraph(data["email"], styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("<b>Education</b>", styles["Heading2"]))
    for e in data.get("education", []):
        content.append(Paragraph(f"- {e}", styles["Normal"]))

    content.append(Paragraph("<b>Technical Skills</b>", styles["Heading2"]))
    content.append(Paragraph(", ".join(data.get("technical_skills", [])), styles["Normal"]))

    if data.get("skills_acquired"):
        content.append(Paragraph("<b>Skills Acquired in Role</b>", styles["Heading2"]))
        for s in data["skills_acquired"]:
            content.append(Paragraph(f"- {s}", styles["Normal"]))

    if data.get("achievements"):
        content.append(Paragraph("<b>Achievements</b>", styles["Heading2"]))
        for a in data["achievements"]:
            content.append(Paragraph(f"- {a}", styles["Normal"]))

    content.append(Paragraph("<b>Experience</b>", styles["Heading2"]))
    for exp in data.get("experience", []):
        content.append(Paragraph(f"- {exp}", styles["Normal"]))

    doc.build(content)

    return jsonify({"status": "success", "file": "/download-api-resume"})

@app.route("/download-api-resume")
def download_api_resume():
    return send_file("uploads/API_Generated_Resume.pdf", as_attachment=True)

# ================= OTHER =================
@app.route("/architecture")
def architecture():
    if not login_required():
        return redirect("/login")
    return render_template("architecture.html")

@app.route("/download-report")
def download_report():
    return send_file("uploads/InternGuide_Report.pdf", as_attachment=True)

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
