from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Date, func
from sqlalchemy.orm import relationship

from app.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)


class GoogleToken(Base):
    __tablename__ = "google_tokens"

    id = Column(Integer, primary_key=True)
    token_json = Column(Text, nullable=False)


class DriveSession(Base):
    __tablename__ = "drive_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    token_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class TarjetaUsuario(Base):
    __tablename__ = "tarjetas_usuarios"

    id = Column(Integer, primary_key=True)
    numero_tarjeta = Column(String, unique=True, nullable=False)
    nombre_usuario = Column(String, nullable=False)
    email_usuario = Column(String, nullable=False)


class Resumen(Base):
    __tablename__ = "resumenes"

    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False)  # AMEX / VISA
    periodo = Column(String, nullable=False)
    archivo_nombre = Column(String, nullable=False)
    fecha_procesado = Column(DateTime, server_default=func.now())

    transacciones = relationship("Transaccion", back_populates="resumen")


class Transaccion(Base):
    __tablename__ = "transacciones"

    id = Column(Integer, primary_key=True)
    resumen_id = Column(Integer, ForeignKey("resumenes.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    descripcion = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    numero_tarjeta = Column(String, nullable=True)
    moneda = Column(String, nullable=False)
    tipo = Column(String, nullable=False)  # AMEX / VISA / Mastercard / etc
    cantidad_cuotas = Column(Integer, nullable=True, default=1)
    cuotas_faltantes = Column(Integer, nullable=True, default=0)
    cuota_numero = Column(Integer, nullable=True, default=1)

    resumen = relationship("Resumen", back_populates="transacciones")
    conciliaciones = relationship("Conciliacion", back_populates="transaccion")


class Factura(Base):
    __tablename__ = "facturas"

    id = Column(Integer, primary_key=True)
    drive_file_id = Column(String, unique=True, nullable=False)
    drive_file_name = Column(String, nullable=False)
    periodo = Column(String, nullable=False)
    fecha_descargado = Column(DateTime, server_default=func.now())
    markdown_text = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)

    datos = relationship("FacturaDatos", back_populates="factura")
    conciliaciones = relationship("Conciliacion", back_populates="factura")


class FacturaDatos(Base):
    __tablename__ = "facturas_datos"

    id = Column(Integer, primary_key=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=False)
    monto_total = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=True)
    tipo_factura = Column(String, nullable=True)
    fecha = Column(String, nullable=False)
    vencimiento = Column(String, nullable=True)
    emisor = Column(String, nullable=True)
    cuit_emisor = Column(String, nullable=True)
    moneda = Column(String, nullable=True)
    numero_factura = Column(String, nullable=True)
    cuota_numero = Column(Integer, nullable=True, default=None)

    factura = relationship("Factura", back_populates="datos")


class Conciliacion(Base):
    __tablename__ = "conciliaciones"

    id = Column(Integer, primary_key=True)
    transaccion_id = Column(Integer, ForeignKey("transacciones.id"), nullable=False)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=True)
    fecha_match = Column(DateTime, server_default=func.now())
    estado = Column(String, nullable=False)  # MATCHED / UNMATCHED
    confianza = Column(Float, nullable=False)
    metodo = Column(String, nullable=False)  # CODE / LLM

    transaccion = relationship("Transaccion", back_populates="conciliaciones")
    factura = relationship("Factura", back_populates="conciliaciones")
