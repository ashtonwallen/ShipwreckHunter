from backend import db,analysis
for d in db.all_records('dataset'):print(d['name'],d['bounds'])
import fitz
p=fitz.open('data/research/H11277-report.pdf');p[19].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save('data/exports/report-page20.png')
