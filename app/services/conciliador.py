from dataclasses import dataclass
from datetime import datetime
import logging

from sqlalchemy import select

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    transaccion_id: int
    factura_id: int | None
    estado: str
    confianza: float
    metodo: str


class Conciliador:
    TOLERANCIA_DIAS = 3
    UMBRAL_CONFIANZA_CODE = 0.95

    @staticmethod
    async def conciliar(
        resumen_id: int,
        db,
        llm_router=None,
    ) -> list[MatchResult]:
        from app.models import Transaccion, FacturaDatos, Conciliacion

        result = await db.execute(
            select(Transaccion).where(Transaccion.resumen_id == resumen_id)
        )
        transacciones = result.scalars().all()

        if not transacciones:
            return []

        from app.models import Resumen as ResumenModel
        res_result = await db.execute(
            select(ResumenModel).where(ResumenModel.id == resumen_id)
        )
        resumen_row = res_result.scalar_one_or_none()
        periodo = resumen_row.periodo if resumen_row else ""

        facturas_result = await db.execute(
            select(FacturaDatos).where(FacturaDatos.fecha.like(f"%{periodo}%"))
        )
        facturas = facturas_result.scalars().all()

        resultados: list[MatchResult] = []

        for t in transacciones:
            matched, confianza = await Conciliador._match_code(t, facturas)

            if matched is None and confianza == 0.0:
                candidatos = Conciliador._find_candidates(t, facturas)
                if candidatos and llm_router:
                    matched, confianza = await Conciliador._match_llm(
                        t, candidatos, llm_router
                    )

            if matched:
                estado = "MATCHED"
                metodo = "LLM" if confianza < Conciliador.UMBRAL_CONFIANZA_CODE else "CODE"
            else:
                estado = "UNMATCHED"
                confianza = 0.0
                metodo = "CODE"

            conc = Conciliacion(
                transaccion_id=t.id,
                factura_id=matched.id if matched else None,
                estado=estado,
                confianza=confianza,
                metodo=metodo,
            )
            db.add(conc)
            await db.flush()

            resultados.append(
                MatchResult(
                    transaccion_id=t.id,
                    factura_id=matched.id if matched else None,
                    estado=estado,
                    confianza=confianza,
                    metodo=metodo,
                )
            )

        await db.commit()
        return resultados

    @staticmethod
    async def _match_code(transaccion, facturas_datos: list) -> tuple:
        candidatos = []
        es_cuota = (transaccion.cantidad_cuotas or 1) > 1

        for fd in facturas_datos:
            if es_cuota:
                # Match por cuotas: monto_cuota × cantidad_cuotas ≈ monto_total_factura
                monto_total_estimado = abs(transaccion.monto) * transaccion.cantidad_cuotas
                monto_factura = abs(fd.monto_total or 0)
                monto_diff = abs(monto_factura - monto_total_estimado)
                monto_tolerance = monto_total_estimado * 0.05
            else:
                # Match normal: monto exacto
                monto_diff = abs(abs(fd.monto_total or 0) - abs(transaccion.monto))
                monto_tolerance = abs(transaccion.monto) * 0.01

            if monto_diff > monto_tolerance:
                continue

            try:
                fecha_fd = datetime.strptime(fd.fecha.split("T")[0], "%Y-%m-%d").date()
            except (ValueError, IndexError):
                try:
                    fecha_fd = datetime.strptime(fd.fecha.split("/")[0], "%d").date()
                    fecha_fd = fecha_fd.replace(
                        year=transaccion.fecha.year, month=transaccion.fecha.month
                    )
                except (ValueError, IndexError):
                    continue

            diff_dias = abs((transaccion.fecha - fecha_fd).days)
            if diff_dias > Conciliador.TOLERANCIA_DIAS:
                continue

            candidatos.append(fd)

        if len(candidatos) == 1:
            return candidatos[0], Conciliador.UMBRAL_CONFIANZA_CODE
        elif len(candidatos) == 0:
            return None, 0.0
        else:
            # Si hay múltiples candidatos, preferir el que tenga cuota_numero coincidente
            for fd in candidatos:
                if es_cuota and fd.cuota_numero == transaccion.cuota_numero:
                    return fd, 0.90
            return None, 0.0

    @staticmethod
    def _find_candidates(transaccion, facturas_datos: list) -> list:
        candidatos = []
        for fd in facturas_datos:
            monto_diff = abs(abs(fd.monto_total or 0) - abs(transaccion.monto))
            monto_tolerance = abs(transaccion.monto) * 0.05

            if monto_diff > monto_tolerance:
                continue

            try:
                fecha_fd = datetime.strptime(fd.fecha.split("T")[0], "%Y-%m-%d").date()
            except (ValueError, IndexError):
                continue

            diff_dias = abs((transaccion.fecha - fecha_fd).days)
            if diff_dias > Conciliador.TOLERANCIA_DIAS + 2:
                continue

            candidatos.append(fd)
        return candidatos

    @staticmethod
    async def _match_llm(transaccion, candidatos: list, llm_router) -> tuple:
        try:
            prompt = Conciliador._build_llm_prompt(transaccion, candidatos)
            response = await llm_router.chat(
                messages=[{"role": "user", "content": prompt}],
                task_type="reconciliation",
                max_tokens=500
            )
            result = Conciliador._parse_llm_response(response, candidatos)
            return result
        except Exception:
            logger.warning("LLM match falló", exc_info=True)
            return None, 0.0

    @staticmethod
    def _build_llm_prompt(transaccion, candidatos: list) -> str:
        facturas_texto = "\n".join(
            f"[{i}] Factura: fecha={fd.fecha}, emisor={fd.emisor}, "
            f"monto=${fd.monto_total}, num={fd.numero_factura}"
            for i, fd in enumerate(candidatos)
        )
        return (
            f"Seleccioná la factura que corresponde a esta transacción bancaria:\n\n"
            f"TRANSACCIÓN:\n"
            f"  Fecha: {transaccion.fecha}\n"
            f"  Descripción: {transaccion.descripcion}\n"
            f"  Monto: ${transaccion.monto}\n"
            f"  Moneda: {transaccion.moneda}\n\n"
            f"FACTURAS CANDIDATAS:\n{facturas_texto}\n\n"
            f"Respondé SOLO con el número de índice de la factura que corresponde, "
            f"o 'ninguna' si ninguna coincide."
        )

    @staticmethod
    def _parse_llm_response(response: str, candidatos: list) -> tuple:
        clean = response.strip().lower()
        clean = clean.split("\n")[0].strip()

        if clean in ("ninguna", "ninguno", "none", "n/a", "-"):
            return None, 0.0

        try:
            idx = int(clean)
            if 0 <= idx < len(candidatos):
                return candidatos[idx], 0.85
        except ValueError:
            pass

        for i, fd in enumerate(candidatos):
            if fd.numero_factura and fd.numero_factura in clean:
                return fd, 0.85

        return None, 0.0
