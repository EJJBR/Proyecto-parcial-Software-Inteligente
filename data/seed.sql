-- Datos de prueba: catalogo de 15 productos, 4 semanas de ventas, un usuario y una solicitud.
-- No incluye RECOMENDACION / DETALLE_RECOMENDACION: la recomendacion que traia bodega.db
-- fue generada con la logica anterior (fitness 930.71) y debe regenerarse con el backend.

INSERT INTO USUARIO (id_usuario, nombre_bodega, ubicacion) VALUES (1,'Bodega La Esquina','Lima, Peru');

INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (1,'abarrotes');
INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (2,'lacteos');
INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (3,'panaderia');
INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (4,'bebidas');
INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (5,'limpieza');
INSERT INTO CATEGORIA (id_categoria, nombre) VALUES (6,'snacks');

INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (1,'Arroz',1,3.5,4.5,'bajo',20,5);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (2,'Leche Gloria 1L',2,4.2,5.0,'alto',3,7);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (3,'Aceite',1,8.0,9.5,'bajo',20,11);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (4,'Fideos',1,2.8,3.5,'bajo',20,8);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (5,'Atún',1,4.5,5.5,'bajo',20,9);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (6,'Pan de molde',3,3.8,4.8,'alto',3,10);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (7,'Yogurt Gloria',2,5.2,6.5,'medio',7,11);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (8,'Gaseosa Coca-Cola 1.5L',4,4.8,5.5,'bajo',20,6);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (9,'Detergente',5,6.5,8.0,'bajo',20,13);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (10,'Galletas Oreo',6,3.0,3.5,'medio',7,9);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (11,'Huevos (docena)',1,6.0,7.0,'medio',7,10);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (12,'Queso fresco',2,9.0,11.0,'alto',3,12);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (13,'Azúcar',1,3.2,4.0,'bajo',20,12);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (14,'Papas Lay''s',6,3.2,4.0,'bajo',20,7);
INSERT INTO PRODUCTO (id_producto, nombre, id_categoria, precio_compra, precio_venta, perecibilidad, dias_vida_util, stock_actual) VALUES (15,'Inca Kola 1.5L',4,4.0,5.2,'bajo',20,9);

INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (1,1,'2026-S1',8);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (2,1,'2026-S2',8);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (3,1,'2026-S3',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (4,1,'2026-S4',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (5,2,'2026-S1',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (6,2,'2026-S2',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (7,2,'2026-S3',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (8,2,'2026-S4',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (9,3,'2026-S1',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (10,3,'2026-S2',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (11,3,'2026-S3',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (12,3,'2026-S4',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (13,4,'2026-S1',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (14,4,'2026-S2',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (15,4,'2026-S3',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (16,4,'2026-S4',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (17,5,'2026-S1',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (18,5,'2026-S2',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (19,5,'2026-S3',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (20,5,'2026-S4',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (21,6,'2026-S1',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (22,6,'2026-S2',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (23,6,'2026-S3',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (24,6,'2026-S4',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (25,7,'2026-S1',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (26,7,'2026-S2',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (27,7,'2026-S3',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (28,7,'2026-S4',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (29,8,'2026-S1',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (30,8,'2026-S2',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (31,8,'2026-S3',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (32,8,'2026-S4',7);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (33,9,'2026-S1',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (34,9,'2026-S2',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (35,9,'2026-S3',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (36,9,'2026-S4',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (37,10,'2026-S1',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (38,10,'2026-S2',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (39,10,'2026-S3',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (40,10,'2026-S4',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (41,11,'2026-S1',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (42,11,'2026-S2',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (43,11,'2026-S3',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (44,11,'2026-S4',4);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (45,12,'2026-S1',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (46,12,'2026-S2',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (47,12,'2026-S3',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (48,12,'2026-S4',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (49,13,'2026-S1',3);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (50,13,'2026-S2',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (51,13,'2026-S3',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (52,13,'2026-S4',2);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (53,14,'2026-S1',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (54,14,'2026-S2',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (55,14,'2026-S3',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (56,14,'2026-S4',6);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (57,15,'2026-S1',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (58,15,'2026-S2',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (59,15,'2026-S3',5);
INSERT INTO VENTA_HISTORICA (id_venta, id_producto, semana, cantidad_vendida) VALUES (60,15,'2026-S4',4);

INSERT INTO SOLICITUD (id_solicitud, id_usuario, fecha, presupuesto, texto_original) VALUES (1,1,'2026-09-21',1500.0,'Tengo S/1500 para reponer esta semana, prioriza lacteos y abarrotes, asegurate de incluir arroz');

INSERT INTO SOLICITUD_CATEGORIA_PRIORITARIA (id_solicitud, id_categoria) VALUES (1,2);
INSERT INTO SOLICITUD_CATEGORIA_PRIORITARIA (id_solicitud, id_categoria) VALUES (1,1);

INSERT INTO SOLICITUD_PRODUCTO_REGLA (id_solicitud, id_producto, tipo_regla) VALUES (1,1,'incluir_forzado');
