import re
import cv2


def ameliorer_image_plaque(plate_img):
    resized = cv2.resize(plate_img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def formater_plaque_tunisienne(texte: str) -> str:
    if not texte:
        return ""
    chiffres = re.findall(r"\d+", texte)
    a_mot_tn = ("تونس" in texte) or ("TN" in texte.upper()) or ("TUN" in texte.upper())
    if len(chiffres) >= 2 and a_mot_tn:
        return f"{chiffres[0][:3]} تونس {chiffres[1][:4]}"
    return re.sub(r"\s+", " ", texte).strip()


def detecter_voiture_et_plaque(frame):
    annotated = frame.copy()
    h, w, _ = frame.shape

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    x, y, cw, ch = int(w * 0.18), int(h * 0.22), int(w * 0.64), int(h * 0.56)
    meilleure_aire = 0
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aire = bw * bh
        if aire > meilleure_aire and bw > w * 0.25 and bh > h * 0.20 and aire < (w * h * 0.9):
            meilleure_aire = aire
            x, y, cw, ch = bx, by, bw, bh

    cv2.rectangle(annotated, (x, y), (x + cw, y + ch), (46, 204, 113), 2)
    cv2.putText(
        annotated,
        "Vehicule",
        (x, max(18, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (46, 204, 113),
        2,
    )

    roi_y1 = y + int(ch * 0.55)
    roi_y2 = min(h, y + ch)
    roi_x1 = x + int(cw * 0.22)
    roi_x2 = min(w, x + int(cw * 0.78))

    plate_roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
    if plate_roi.size == 0:
        plate_roi = frame

    cv2.rectangle(annotated, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 165, 0), 2)
    plate_amelioree = ameliorer_image_plaque(plate_roi)

    return annotated, plate_amelioree, ""