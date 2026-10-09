from backend import db
import fitz
p=fitz.open('data/research/H11277-report.pdf')
p[20].get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save('data/exports/report-page21.png')
p[157].get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save('data/exports/report-page158.png')
