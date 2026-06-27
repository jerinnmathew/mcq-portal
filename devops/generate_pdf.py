import os
import re
import json
import base64
import urllib.request
from fpdf import FPDF

class PDFReport(FPDF):
    def header(self):
        # Header banner on every page except cover page
        if self.page_no() > 1:
            self.set_font("helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, "MCQ Battle Platform - Academic Project Report", border=0, ln=1, align="R")
            self.line(10, 15, 200, 15)
            self.ln(5)

    def footer(self):
        # Footer on every page
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.line(10, self.get_y() - 2, 200, self.get_y() - 2)
        # Page number
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", border=0, align="C")

def get_mermaid_image(mermaid_code):
    """Encodes Mermaid code and downloads the rendered diagram as a PNG."""
    image_path = "c:\\Desktop\\mcq-portal\\devops\\architecture_diagram.png"
    
    # Try downloading the image via mermaid.ink
    try:
        config = {
            "code": mermaid_code,
            "mermaid": {"theme": "default"},
            "updateEditor": False,
            "autoSync": True,
            "updateDiagram": False
        }
        json_str = json.dumps(config)
        json_bytes = json_str.encode('utf-8')
        base64_bytes = base64.b64encode(json_bytes)
        base64_string = base64_bytes.decode('utf-8')
        
        url = f"https://mermaid.ink/img/{base64_string}"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(image_path, "wb") as f:
                f.write(response.read())
        return image_path
    except Exception as e:
        print(f"Warning: Could not fetch online Mermaid diagram: {e}. Using local cache or fallback.")
        if os.path.exists(image_path):
            return image_path
        return None

def build_pdf():
    pdf = PDFReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.alias_nb_pages()
    
    # ------------------ COVER PAGE ------------------
    pdf.add_page()
    pdf.ln(30)
    
    # Title
    pdf.set_font("helvetica", "B", 26)
    pdf.set_text_color(26, 54, 93) # Dark Blue
    pdf.multi_cell(0, 15, "MCQ BATTLE PLATFORM", border=0, align="C")
    
    # Subtitle
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(74, 85, 104) # Slate Gray
    pdf.multi_cell(0, 8, "Comprehensive Academic Project Report\nMulti-Tier AWS Infrastructure, Secure Hosting, and CI/CD Automation", border=0, align="C")
    
    pdf.ln(30)
    
    # Decorative line
    pdf.set_draw_color(26, 54, 93)
    pdf.set_fill_color(26, 54, 93)
    pdf.rect(30, 95, 150, 2, "F")
    
    pdf.ln(35)
    
    # Meta Details Card
    pdf.set_fill_color(247, 250, 252) # Soft Gray
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(20, 125, 170, 95, "DF")
    
    pdf.set_xy(25, 130)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "PROJECT METADATA", ln=1)
    
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)
    
    details = [
        ("Course Name:", "Academic Project Submissions 2026"),
        ("Project Title:", "SEA-1 MCQ Battle Platform"),
        ("Deployment URL:", "https://mcq-platform.duckdns.org"),
        ("Host Platform:", "AWS EC2 Ubuntu Application Server"),
        ("Database Engine:", "AWS RDS MySQL (Private Tier)"),
        ("Orchestration:", "Gunicorn, Nginx, Let's Encrypt (SSL/TLS), Docker"),
        ("CI/CD Pipeline:", "GitHub Actions Automation"),
        ("Security Standards:", "scrypt, HttpOnly Secure JWT, CSRF Shields, Rate Limiter"),
    ]
    
    for label, val in details:
        pdf.set_x(25)
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(74, 85, 104)
        pdf.cell(40, 7, label, 0, 0)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(26, 32, 44)
        pdf.cell(0, 7, val, 0, 1)
    
    pdf.ln(10)
    pdf.set_x(25)
    pdf.set_font("helvetica", "I", 9)
    pdf.set_text_color(113, 128, 150)
    pdf.cell(0, 6, "Generated automatically for deployment evaluation on May 29, 2026", ln=1)
    
    # ------------------ END COVER PAGE ------------------

    # Read the markdown file
    md_path = "c:\\Desktop\\mcq-portal\\devops\\project_report.md"
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return
        
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split the file into paragraphs/blocks
    blocks = content.split("\n\n")
    
    # Set default values for main page writing
    pdf.add_page()
    pdf.set_text_color(45, 55, 72) # Slate Gray
    
    in_code_block = False
    in_table = False
    
    code_content = []
    
    def render_paragraph(text):
        # Format bold text
        text = text.replace("&copy;", "©")
        parts = re.split(r"(\*\*.*?\*\*)", text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                pdf.set_font("helvetica", "B", 10)
                clean_part = part[2:-2]
                pdf.write(6, clean_part)
            else:
                pdf.set_font("helvetica", "", 10)
                pdf.write(6, part)
        pdf.ln(8)

    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        # Handle Horizontal Rule
        if block == "---":
            pdf.ln(2)
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
            continue

        # Handle Mermaid Diagram Block Specially
        if block.startswith("```mermaid"):
            mermaid_code = block.replace("```mermaid", "").replace("```", "").strip()
            print("Rendering Mermaid diagram...")
            img_path = get_mermaid_image(mermaid_code)
            if img_path and os.path.exists(img_path):
                # Check vertical space (Mermaid diagram is landscape, w=150, h=95)
                if pdf.get_y() + 105 > 275:
                    pdf.add_page()
                
                # Render Image centered
                x_pos = (210 - 150) / 2
                pdf.image(img_path, x=x_pos, y=pdf.get_y(), w=150)
                pdf.ln(100) # Move cursor past diagram height
                
                # Render Caption
                pdf.set_font("helvetica", "I", 9)
                pdf.set_text_color(113, 128, 150)
                pdf.cell(0, 5, "Figure: Multi-Tier Network & Deployment Architecture", ln=1, align="C")
                pdf.ln(6)
            else:
                # Fallback to code text block if render fails
                pdf.set_font("courier", "", 9)
                pdf.set_text_color(45, 55, 72)
                pdf.set_fill_color(247, 250, 252)
                pdf.multi_cell(0, 5, mermaid_code, border=1, fill=True)
                pdf.ln(4)
            continue
            
        # Handle Code Block
        if block.startswith("```"):
            if not in_code_block:
                in_code_block = True
                # Skip first line if it specifies language
                lines = block.split("\n")[1:]
                code_content.extend(lines)
                if block.endswith("```"):
                    in_code_block = False
                    code_content = [c for c in code_content if c.strip() != "```" and c.strip() != ""]
                    # Render code block
                    pdf.set_font("courier", "", 9)
                    pdf.set_text_color(45, 55, 72)
                    pdf.set_fill_color(247, 250, 252)
                    code_str = "\n".join(code_content)
                    pdf.multi_cell(0, 5, code_str, border=1, fill=True)
                    pdf.ln(4)
                    code_content = []
            else:
                in_code_block = False
                # Render code block
                pdf.set_font("courier", "", 9)
                pdf.set_text_color(45, 55, 72)
                pdf.set_fill_color(247, 250, 252)
                code_str = "\n".join(code_content)
                pdf.multi_cell(0, 5, code_str, border=1, fill=True)
                pdf.ln(4)
                code_content = []
            continue
            
        if in_code_block:
            lines = block.split("\n")
            code_content.extend(lines)
            continue

        # Handle Table
        if "|" in block:
            lines = block.split("\n")
            if len(lines) >= 3 and "|" in lines[0]:
                # Render Table
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(26, 54, 93)
                pdf.set_fill_color(240, 244, 248)
                
                headers = [h.strip() for h in lines[0].split("|")[1:-1]]
                widths = [45, 95, 50]
                
                # Write Header Row
                for idx, h in enumerate(headers):
                    pdf.cell(widths[idx], 8, h, border=1, fill=True, align="L")
                pdf.ln()
                
                pdf.set_font("helvetica", "", 8.5)
                pdf.set_text_color(45, 55, 72)
                
                # Write Data Rows
                for row_line in lines[2:]:
                    row_cells = [c.strip() for c in row_line.split("|")[1:-1]]
                    if len(row_cells) < len(headers):
                        continue
                    
                    # Calculate row height
                    max_lines = 1
                    for idx, c in enumerate(row_cells):
                        words_len = len(c)
                        char_limit = int(widths[idx] * 1.5)
                        lines_cnt = max(1, (words_len // char_limit) + 1)
                        if lines_cnt > max_lines:
                            max_lines = lines_cnt
                    
                    row_height = max_lines * 5
                    
                    x_before = pdf.get_x()
                    y_before = pdf.get_y()
                    
                    if y_before + row_height > 275:
                        pdf.add_page()
                        y_before = pdf.get_y()
                    
                    for idx, c in enumerate(row_cells):
                        pdf.set_xy(x_before + sum(widths[:idx]), y_before)
                        pdf.multi_cell(widths[idx], row_height / max_lines, c, border=1, fill=False)
                    
                    pdf.set_xy(x_before, y_before + row_height)
                pdf.ln(4)
                continue

        # Handle Images
        if block.startswith("!["):
            img_match = re.search(r"\!\[(.*?)\]\((.*?)\)", block)
            if img_match:
                caption = img_match.group(1)
                img_path = img_match.group(2)
                
                # Convert file:/// path to absolute path
                if img_path.startswith("file:///"):
                    img_path = img_path.replace("file:///", "").replace("/", "\\")
                
                if os.path.exists(img_path):
                    # Check vertical space
                    if pdf.get_y() + 85 > 275:
                        pdf.add_page()
                    
                    # Render Image centered
                    x_pos = (210 - 130) / 2
                    pdf.image(img_path, x=x_pos, y=pdf.get_y(), w=130)
                    pdf.ln(80)
                    
                    # Render caption
                    pdf.set_font("helvetica", "I", 9)
                    pdf.set_text_color(113, 128, 150)
                    pdf.cell(0, 5, f"Figure: {caption}", ln=1, align="C")
                    pdf.ln(6)
                else:
                    pdf.set_font("helvetica", "I", 9)
                    pdf.set_text_color(229, 62, 62)
                    pdf.cell(0, 6, f"[Image Placeholder: {caption} (File not found)]", ln=1, align="C")
                    pdf.ln(4)
            continue

        # Handle Headings
        if block.startswith("#"):
            heading_level = len(block) - len(block.lstrip("#"))
            title_text = block.lstrip("#").strip()
            title_text = title_text.replace("**", "").replace("__", "")
            
            if heading_level == 1:
                pdf.ln(10)
                pdf.set_font("helvetica", "B", 18)
                pdf.set_text_color(26, 54, 93)
                pdf.cell(0, 10, title_text, ln=1)
                pdf.line(10, pdf.get_y() - 1, 200, pdf.get_y() - 1)
                pdf.ln(4)
            elif heading_level == 2:
                pdf.ln(6)
                if pdf.get_y() + 40 > 275:
                    pdf.add_page()
                pdf.set_font("helvetica", "B", 14)
                pdf.set_text_color(43, 108, 176)
                pdf.cell(0, 8, title_text, ln=1)
                pdf.ln(2)
            elif heading_level == 3:
                pdf.ln(4)
                pdf.set_font("helvetica", "B", 11)
                pdf.set_text_color(45, 55, 72)
                pdf.cell(0, 6, title_text, ln=1)
                pdf.ln(2)
            elif heading_level >= 4:
                pdf.ln(3)
                pdf.set_font("helvetica", "B", 10)
                pdf.set_text_color(74, 85, 104)
                pdf.cell(0, 5, title_text, ln=1)
                pdf.ln(1.5)
            continue
            
        # Handle Bullet Lists
        if block.startswith("* ") or block.startswith("- "):
            lines = block.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("* ") or line.startswith("- "):
                    bullet_text = line[2:]
                    pdf.set_x(15)
                    pdf.set_font("helvetica", "", 10)
                    pdf.set_text_color(45, 55, 72)
                    pdf.write(6, chr(149) + "  ")
                    
                    bullet_parts = re.split(r"(\*\*.*?\*\*)", bullet_text)
                    for part in bullet_parts:
                        if part.startswith("**") and part.endswith("**"):
                            pdf.set_font("helvetica", "B", 10)
                            pdf.write(6, part[2:-2])
                        else:
                            pdf.set_font("helvetica", "", 10)
                            pdf.write(6, part)
                    pdf.ln(7)
            pdf.ln(2)
            continue

        # Standard Paragraphs
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(45, 55, 72)
        render_paragraph(block)

    # Save PDF
    output_pdf_path = "c:\\Desktop\\mcq-portal\\devops\\MCQ_Battle_Project_Report.pdf"
    pdf.output(output_pdf_path)
    print(f"Success! Beautiful PDF with rendered Mermaid diagram generated at: {output_pdf_path}")

if __name__ == "__main__":
    build_pdf()
