# Traffic--Simulation

---

```
                                                                                         
                                                                                         
            .o.oOo.o.o.oOo.o.o.oOo.o.o.oOo.o.o.oOo.o.o.oOo.o.o.oOo.o.o.oOo.o.            
          'YS000$000S000$000S000$000S000$000S000$000S000$000S000$000S000$000SY'          
           'TP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YTP'YT'           
            |(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|(*)|            
            lb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dlb.dl            
         'YS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SSS$SY'         
           'Y^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^Y'           
            [d0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0bd0b]            
            [Y0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0PY0P]            
             HTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTHHTH             
             HTHTHTHTHTHTHTHTHTHidbdbdbdbdbYHYdbdbdbdbdbiHTHTHTHTHTHTHTHTHTH             
             H.================.idbdbdbPºº'''''ººYdbdbdbi.================.H             
             H||d0bd0bdbd0bd0b||idbdPº             ºYbdbi||d0bd0bdbd0bd0b||H             
             H||Y0PY0PYPY0PY0P||idP'                 'Ybi||Y0PY0PYPY0PY0P||H             
             H'================'HP                     YH'================'H             
             HTHTHTHTHTHTHTHTHTHT'                     'THTHTHTHTHTHTHTHTHTH             
            YS$SSS$SSS$SSS$SSS$SSY                     YSS$SSS$SSS$SSS$SSS$SY            
             H^TT^TT^TTTT^TT^TT^H                       H^TT^TT^TTTT^TT^TT^H             
             HTHTHTHT'db'THTHTHTH                       HTHTHTHT'db'THTHTHTH             
             HTHHT'dbo$$odb'THHTH                       HTHHT'dbo$$odb'THHTH             
             HTHTH CsRGuRoD HTHTH                       HTHTH CsRGuRoD HTHTH             
             HTHHT.dBaRijGb.THHTH                       HTHHT.dBaRijGb.THHTH             
             HTHT dJTuTqaGBb THTH                       HTHT dJTuTqaGBb THTH             
             HTHH.YGDfwPoOCP.HHTH                       HTHH.YGDfwPoOCP.HHTH             
            'YSS$SiS$SSSS$SiS$SSY'                     'YSS$SiS$SSSS$SiS$SSY'            
             HTTT^iTT^TT^TTi^TTTH                       HTTT^iTT^TT^TTi^TTTH             
            .HTHTHiHTHTTHTHiHTHTH.                     .HTHTHiHTHTTHTHiHTHTH.            
            d$SS$SiS$SSSS$SiS$SS$b                     d$SS$SiS$SSSS$SiS$SS$b            
                                                                                         
                                                                                         
```

---

## Requisitos
> agentpy==0.1.5  
> numpy  
> pygame==2.6.1  
> PyOpenGL  
> matplotlib  

---

## Estructura
```diff
  📂 root
  ├— Plan&rules.md
  ├— README.md
  ├— main.py
  ├— train.py
  │
  ├— 📂 sim
  │  ├— car_agent.py
  │  ├— city_model.py
  │  ├— config.py
  │  ├— game_theory.py
  │  ├— objloader.py
  │  ├— renderer.py
  │  ├— road_network.py
  │  └— traffic_light.py
  │
  ├— 📂 assets
  │  ├— 📂 arc_de_triomphe
  │  └— 📂 car
  │     ├— carroceria.obj
  │     ├— llanta_FL.obj
  │     ├— llanta_FR.obj
  │     └— llantas_traseras.obj
  │
  ├— 📂 docs
  │  ├— Activity.md
  │  ├— Ejemplo_coaliciones.pdf
  │  └— Proposal.md
  │
  └— 📂 reference
     ├— 📂 Ejemplo_carro
     └— 📂 Ejemplo_planos_cubos_carro
```
