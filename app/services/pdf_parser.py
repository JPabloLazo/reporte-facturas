import re
from enum import Enum
from dataclasses import dataclass

import pdfplumber


class PDFParseError(Exception):
    pass


class TipoResumen(Enum):
    AMEX = "AMEX"
    VISA = "VISA"


@dataclass
class TransaccionExtraida:
    fecha: str
    descripcion: str
    monto: float
    numero_tarjeta: str | None = None
    moneda: str = "ARS"


class ResumenParser:

    @staticmethod
    def detectar_tipo(file_path: str) -> TipoResumen:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                text_lower = text.lower()
                if "american express" in text_lower or "amex" in text_lower:
                    return TipoResumen.AMEX
                if "visa" in text_lower:
                    return TipoResumen.VISA
        raise ValueError("Tipo de resumen no reconocido")

    @staticmethod
    def _parse_amount(value: str) -> float:
        cleaned = value.replace("$", "").replace("U$S", "").replace(" ", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        if "," in cleaned and "." in cleaned:
            if cleaned.rindex(",") > cleaned.rindex("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)

    @staticmethod
    def _normalize_fecha(raw: str) -> str:
        cleaned = raw.strip()
        match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', cleaned)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = f"20{y}"
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{2,4})', cleaned)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = f"20{y}"
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        return cleaned

    @staticmethod
    def extraer_numero_tarjeta(text: str) -> str | None:
        pattern = r'(?:\d{4}[-\s]?){3}(\d{4})'
        match = re.search(pattern, text)
        if match:
            return f"****{match.group(1)}"
        pattern2 = r'(?:terminada\s*en|nro[.:\s]*|tarjeta[:\s]*)\**(\d{4})'
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            return f"****{match2.group(1)}"
        return None

    @staticmethod
    def parsear_amex(file_path: str) -> list[TransaccionExtraida]:
        transacciones: list[TransaccionExtraida] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue
                for row in table[1:]:
                    if not row or all(c is None or c.strip() == "" for c in row):
                        continue
                    cells = [c.strip() if c else "" for c in row]
                    fecha = ResumenParser._normalize_fecha(cells[0]) if len(cells) > 0 else ""
                    descripcion = cells[1] if len(cells) > 1 else ""
                    monto_str = cells[2] if len(cells) > 2 else ""
                    moneda = "ARS"
                    if len(cells) > 3 and cells[3]:
                        moneda = cells[3].strip()
                    if not fecha or not descripcion or not monto_str:
                        continue
                    try:
                        monto = ResumenParser._parse_amount(monto_str)
                    except (ValueError, IndexError):
                        continue
                    transacciones.append(TransaccionExtraida(
                        fecha=fecha,
                        descripcion=descripcion,
                        monto=monto,
                        moneda=moneda,
                    ))
        if not transacciones:
            transacciones = ResumenParser._fallback_text_extraction(file_path)
        return transacciones

    @staticmethod
    def parsear_visa(file_path: str) -> list[TransaccionExtraida]:
        transacciones: list[TransaccionExtraida] = []
        tarjeta_actual: str | None = None
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                card = ResumenParser.extraer_numero_tarjeta(text)
                if card:
                    tarjeta_actual = card
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue
                for row in table[1:]:
                    if not row or all(c is None or c.strip() == "" for c in row):
                        continue
                    cells = [c.strip() if c else "" for c in row]
                    fecha = ResumenParser._normalize_fecha(cells[0]) if len(cells) > 0 else ""
                    descripcion = cells[1] if len(cells) > 1 else ""
                    monto_str = cells[2] if len(cells) > 2 else ""
                    if not fecha or not descripcion or not monto_str:
                        continue
                    try:
                        monto = ResumenParser._parse_amount(monto_str)
                    except (ValueError, IndexError):
                        continue
                    transacciones.append(TransaccionExtraida(
                        fecha=fecha,
                        descripcion=descripcion,
                        monto=monto,
                        numero_tarjeta=tarjeta_actual,
                    ))
        if not transacciones:
            transacciones = ResumenParser._fallback_text_extraction(file_path)
        return transacciones

    @staticmethod
    def _fallback_text_extraction(file_path: str) -> list[TransaccionExtraida]:
        transacciones: list[TransaccionExtraida] = []
        with pdfplumber.open(file_path) as pdf:
            raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if len(raw_text.strip()) < 10:
            return transacciones
        lines = raw_text.split("\n")

        # Try VISA Argentina format first (DD-Mon-YY)
        meses = "Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic"
        visa_pattern = re.compile(
            rf'(\d{{1,2}}-({meses})-\d{{2,4}})\s+(.+?)\s+([\d.,]+)$'
        )
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = visa_pattern.search(line)
            if match:
                fecha = match.group(1)
                descripcion = match.group(3).strip()
                try:
                    monto = ResumenParser._parse_amount(match.group(4))
                except ValueError:
                    continue
                meses_map = {"Ene":"01","Feb":"02","Mar":"03","Abr":"04","May":"05","Jun":"06",
                             "Jul":"07","Ago":"08","Sep":"09","Oct":"10","Nov":"11","Dic":"12"}
                parts = fecha.split("-")
                if len(parts) == 3 and parts[1] in meses_map:
                    dia = parts[0].zfill(2)
                    mes = meses_map[parts[1]]
                    anio = parts[2]
                    if len(anio) == 2:
                        anio = f"20{anio}"
                    fecha_normalizada = f"{dia}/{mes}/{anio}"
                else:
                    fecha_normalizada = ResumenParser._normalize_fecha(fecha)
                transacciones.append(TransaccionExtraida(
                    fecha=fecha_normalizada,
                    descripcion=descripcion,
                    monto=monto,
                ))
                continue

        if transacciones:
            return transacciones

        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.search(
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+\$?([\d.,]+)\s*$',
                line,
            )
            if match:
                fecha = ResumenParser._normalize_fecha(match.group(1))
                descripcion = match.group(2).strip()
                try:
                    monto = ResumenParser._parse_amount(match.group(3))
                except ValueError:
                    continue
                transacciones.append(TransaccionExtraida(
                    fecha=fecha,
                    descripcion=descripcion,
                    monto=monto,
                ))
        return transacciones

    @staticmethod
    def parsear_fallback_vision(file_path: str, llm_router=None) -> list[TransaccionExtraida]:
        try:
            from pdf2image import convert_from_path
            import io
            import base64
            images = convert_from_path(file_path, dpi=200)
            if llm_router is not None and hasattr(llm_router, "extract_with_vision"):
                if images:
                    buf = io.BytesIO()
                    images[0].save(buf, format='JPEG', quality=85)
                    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    result_str = llm_router.extract_with_vision(img_b64)
                    if result_str:
                        import json
                        try:
                            data = json.loads(result_str)
                            if isinstance(data, list):
                                items = data
                            elif isinstance(data, dict):
                                items = data.get("transacciones", data.get("transactions", []))
                            else:
                                items = []
                            result = []
                            for item in items:
                                result.append(TransaccionExtraida(
                                    fecha=item.get("fecha", ""),
                                    descripcion=item.get("descripcion", item.get("description", "")),
                                    monto=float(item.get("monto", item.get("amount", 0))),
                                    numero_tarjeta=item.get("numero_tarjeta", item.get("card", None)),
                                    moneda=item.get("moneda", item.get("currency", "ARS")),
                                ))
                            if result:
                                return result
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass
        except ImportError:
            pass
        return ResumenParser._fallback_text_extraction(file_path)
