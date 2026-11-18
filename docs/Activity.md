# Evidencia.2. Solución y presentación del reto

## Descripción del reto
La movilidad urbana, se define como la habilidad de transportarse de un lugar a otro y es fundamental para el desarrollo económico y social y la calidad de vida de los habitantes de una ciudad. Desde hace un tiempo, asociar la movilidad con el uso del automóvil ha sido un signo distintivo de progreso. Sin embargo, esta asociación ya no es posible hoy. El crecimiento y uso indiscriminado del automóvil —que fomenta políticas públicas erróneamente asociadas con la movilidad sostenible—genera efectos negativos enormes en los niveles económico, ambiental y social en México.

Durante las últimas décadas, ha existido una tendencia alarmante de un incremento en el uso de automóviles en México. Los Kilómetros-Auto Recorridos (VKT por sus siglas en Inglés) se han triplicado, de 106 millones en 1990, a 339 millones en 2010. Ésto se correlaciona simultáneamente con un incremento en los impactos negativos asociados a los autos, como el smog, accidentes, enfermedades y congestión vehicular.

Para que México pueda estar entre las economías más grandes del mundo, es necesario mejorar la movilidad en sus ciudades, lo que es crítico para las actividades económicas y la calidad de vida de millones de personas.

Este reto te permitirá proponer una solución al problema de movilidad urbana en México, mediante un enfoque que reduzca la congestión vehicular al simular de manera gráfica el tráfico, representando la salida de un sistema multi agentes.

### Descripción de la evidencia (multiagentes)
Propuesta formal de solución del reto, que debe considerar:
- Descripción del reto a desarrollar. Describan la ciudad en la que situarán a los agentes (ver descripción y restricciones en el siguiente apartado).
- Identificación de los agentes involucrados. Identificar de manera completa los agentes y las posibles relaciones entre los mismos: descripción de su autonomía, mecanismos de negociación, arquitectura de coordinación. Detalla cuáles sería los agentes involucrados, qué tipo de agente serían y la forma de interacción entre ellos.
- Descripción de los mecanismos y estrategias de comunicación y colaboración entre agentes necesarios para el control del tráfico.
- Descripción clara del conjunto de políticas de control de tráfico y la gestión de prioridades.
- Modelación del sistema multiagentes necesario para simular el control de tráfico.
- Diagrama de clase presentando los distintos agentes involucrados.
- Plan de trabajo.
Implementación de los agentes modelados (Python-Agentpy).

### Descripción de la evidencia (gráficas computacionales)
Implementación visual de la ciudad que se usará como base para las simulaciones que se llevarán a cabo dentro de las actividades del reto. Para ello, se recomienda tomar en cuenta las siguientes recomendaciones sobre el diseño de su ciudad:
- Descripción de la ciudad a implementar: se espera que los estudiantes seleccionen parte de una ciudad con calles e intersecciones, que permita llevar a cabo una serie de simulaciones para probar los diferentes escenarios que afectan al tránsito vehícular. El diseño puede ser tomado de un escenario real (parte de alguna ciudad) o bien, una propuesta ficticia. Se recomienda que se implementen en su ciudad calles que permitan a los carritos transitar en un circuito, es decir, que puedan dar vueltas (circuitos de recorrido) dentro de su ciudad.
- No existe una dimensión máxima de la ciudad a implementar, pero si se espera que existan diferentes intersecciones (esquinas), dónde los automóviles a simular tengan que cambiar de dirección (con un control de semáforos para decidir quién tiene el paso). Por lo menos, se espera que existan 6 intersecciones en su ciudad. Los tipos de intersección contemplados son esquinas tradicionales (intersecciones tipo cruz, tipo T), bien intersecciones tipo rotondas. Sin embargo, para este tipo de intersección, el control es más complejo.
- Los sentidos de las calles pueden ser de un solo sentido (calles sencillas), de doble sentido, o bien avenidas que puedan tener 4 o más carriles. Se recomienda que simplifiquen su diseño, para que no sea compleja la implementación considerando el tiempo disponible para su desarrollo.
- En una ciudad real existen pasos a desnivel (puentes) o intersecciones tipo glorietas de varios niveles. Para su propuesta de la ciudad, es posible considerar este tipo de intersecciones/glorietas, pero se debe tomar en cuenta que el diseño y control es más complejo. Por tanto, se recomienda evitar su uso.

Con respecto a los productos que los equipos deberán de desarrollar para su reto, se espera lo siguiente:
1. Implementación de una ciudad 3D, donde se observen: calles, edificios, infraestructura urbana (semáforos, árboles, farolas, etc). Los elementos a usar dependerán del diseño de su ciudad.
2. Automóviles: se espera que se muestre un número “n” de carritos en la ciudad, los cuales circulen de acuerdo a las reglas de actuación de los agentes. El número de carritos puede variar, dependiendo de la simulación a realizar. Los carritos deben simular su movimiento, cambios de carril, vueltas, etc. Se debe diseñar el control de los carritos a partir de una máquina de estados optimizada (control gráfico).
3. Se deberá de mostrar en la escena como cambian aspectos de control de la ciudad, como el cambio de color de los semáforos. Recuerda que toda la documentación que generen en torno al reto deberá mantener consistencia gráfica en aspectos como fuentes tipográficas, colores o sombreados, imágenes, márgenes y alineación.

---

## Instrumento de evaluación
Para la evaluación de las evidencias se hará uso de rúbricas generales con descriptores que muestran desempeños clave y criterios que distinguen tu grado de logro en las subcompetencias, ya sea Destacado, Sólido, Básico o Incipiente.

| Subcompetencia | Destacado | Sólido  | Básico | Incipiente |
| --- | ---- | --- | --- | --- |
| STC0104 Implementación de modelos computacionales | Implementa modelos computacionales que operan de manera estratégica con otros modelos computacionales que resuelven con exactitud un problema que se delimita con claridad. | Implementa modelos computacionales que operan de manera articulada con otros modelos computacionales para resolver de forma correcta un problema que se delimita con claridad. | Implementa modelos computacionales que operan de manera articulada con otros modelos computacionales; sin embargo, presentan errores menores en la interoperabilidad, por lo que logra resolver de forma parcial un problema que se plantea. | Implementa modelos computacionales que operan de manera desarticulada con otros modelos computacionales, por lo que no logra resolver el problema que se plantea. |
| SEG0501 Pensamiento sistémico | Explica de forma óptima un fenómeno, situación o problema; a partir de identificar, con exactitud el conjunto de variables intervinientes relevantes y de establecer, de modo integral, las interrelaciones que mantienen, así como de exponer de forma articulada las conexiones sistémicas con diferentes disciplinas. | Explica de forma correcta un fenómeno, situación o problema; a partir de identificar, con claridad el conjunto de variables intervinientes relevantes y de establecer, con errores menores, las interrelaciones que mantienen, así como de exponer de forma estructurada las conexiones sistémicas con diferentes disciplinas. | Explica de forma limitada un fenómeno, situación o problema; a partir de identificar con imprecisiones las variables intervinientes pertinentes y de establecer, de modo parcial, las interrelaciones que mantienen, así como de exponer de forma coherente las conexiones sistémicas con diferentes disciplinas. | Explica de forma incorrecta un fenómeno, situación o problema; a partir de identificar algunas de las variables intervinientes pertinentes y/o de establecer, con errores, las interrelaciones que mantienen, o bien, de exponer de forma confusa las conexiones sistémicas con diferentes disciplinas. |
