#!/usr/bin/env python3
"""Single source for references.bib and the reference list of the brief.

Each entry: key, type, fields, status (V or V-bib), note (what was read, where verified).
Only entries listed in ENTRIES go to references.bib. UNVERIFIED items are listed
in the brief only.
"""
import re, sys, pathlib

A = "article"; P = "inproceedings"; M = "misc"; T = "mastersthesis"

def e(key, typ, status, note, **f):
    return dict(key=key, typ=typ, status=status, note=note, f=f)

ENTRIES = [
 # ---- lossless, raw events
 e("bi2018", P, "V", "Crossref and author-hosted full text. Table 1 re-read for this brief.",
   author="Bi, Z. and Dong, S. and Tian, Y. and Huang, T.", title="Spike Coding for Dynamic Vision Sensors",
   booktitle="2018 Data Compression Conference (DCC)", pages="117--126", year="2018", doi="10.1109/DCC.2018.00020"),
 e("dong2019", A, "V-bib", "Crossref. Primary full text not obtained. Content is second-hand via brites2025.",
   author="Dong, S. and Bi, Z. and Tian, Y. and Huang, T.", title="Spike Coding for Dynamic Vision Sensor in Intelligent Driving",
   journal="IEEE Internet of Things Journal", volume="6", number="1", pages="60--71", year="2019", doi="10.1109/JIOT.2018.2872984"),
 e("khan2020", A, "V", "Crossref and publisher PDF in the Kingston repository (full text).",
   author="Khan, N. and Iqbal, K. and Martini, M. G.", title="Lossless Compression of Data From Static and Mobile Dynamic Vision Sensors-Performance and Trade-Offs",
   journal="IEEE Access", volume="8", pages="103149--103163", year="2020", doi="10.1109/ACCESS.2020.2996661"),
 e("iqbal2020", P, "V-bib", "Crossref. Abstract level only.",
   author="Iqbal, K. and Khan, N. and Martini, M. G.", title="Performance Comparison of Lossless Compression Strategies for Dynamic Vision Sensor Data",
   booktitle="ICASSP 2020 - IEEE International Conference on Acoustics, Speech and Signal Processing", pages="4427--4431", year="2020", doi="10.1109/ICASSP40776.2020.9053178"),
 e("khan2021talven", A, "V", "Crossref and accepted manuscript (full text).",
   author="Khan, N. and Iqbal, K. and Martini, M. G.", title="Time-Aggregation-Based Lossless Video Encoding for Neuromorphic Vision Sensor Data",
   journal="IEEE Internet of Things Journal", volume="8", number="1", pages="596--609", year="2021", doi="10.1109/JIOT.2020.3007866"),
 e("martini2022", A, "V-bib", "Crossref and DOAJ. Abstract level. The 49.4% figure is second-hand.",
   author="Martini, M. and Adhuran, J. and Khan, N.", title="Lossless Compression of Neuromorphic Vision Sensor Data Based on Point Cloud Representation",
   journal="IEEE Access", volume="10", pages="121352--121364", year="2022", doi="10.1109/ACCESS.2022.3222330"),
 e("adhuran2024", A, "V", "Crossref and MDPI page (full text).",
   author="Adhuran, J. and Khan, N. and Martini, M. G.", title="Lossless Encoding of Time-Aggregated Neuromorphic Vision Sensor Data Based on Point-Cloud Compression",
   journal="Sensors", volume="24", number="5", pages="1382", year="2024", doi="10.3390/s24051382"),
 e("schiopu2022spl", A, "V-bib", "Crossref. Content second-hand.",
   author="Schiopu, I. and Bilcu, R. C.", title="Lossless Compression of Event Camera Frames",
   journal="IEEE Signal Processing Letters", volume="29", pages="1779--1783", year="2022", doi="10.1109/LSP.2022.3196599"),
 e("schiopu2022lsens", A, "V-bib", "Crossref. Content second-hand.",
   author="Schiopu, I. and Bilcu, R. C.", title="Low-Complexity Lossless Coding for Memory-Efficient Representation of Event Camera Frames",
   journal="IEEE Sensors Letters", volume="6", number="11", pages="1--4", year="2022", doi="10.1109/LSENS.2022.3216894"),
 e("schiopu2022sensors", A, "V", "Crossref and MDPI page. Abstract and method read. Experimental section not visible.",
   author="Schiopu, I. and Bilcu, R. C.", title="Low-Complexity Lossless Coding of Asynchronous Event Sequences for Low-Power Chip Integration",
   journal="Sensors", volume="22", number="24", pages="10014", year="2022", doi="10.3390/s222410014"),
 e("schiopu2023cvprw", P, "V", "Crossref and CVF open-access PDF (full text). Table 3 re-read for this brief.",
   author="Schiopu, I. and Bilcu, R. C.", title="Entropy Coding-based Lossless Compression of Asynchronous Event Sequences",
   booktitle="2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="3923--3930", year="2023", doi="10.1109/CVPRW59228.2023.00407"),
 e("schiopu2023electronics", A, "V", "Crossref and MDPI page (abstract).",
   author="Schiopu, I. and Bilcu, R. C.", title="Memory-Efficient Fixed-Length Representation of Synchronous Event Frames for Very-Low-Power Chip Integration",
   journal="Electronics", volume="12", number="10", pages="2302", year="2023", doi="10.3390/electronics12102302"),
 e("schiopu2024cadett", A, "V-bib", "Crossref. Content not read.",
   author="Schiopu, I. and Bilcu, R. C.", title="{CADeTT}: Context-Adaptive Deep-Trinary-Tree Lossless Compression of Event Camera Frames",
   journal="IEEE Signal Processing Letters", volume="31", pages="3149--3153", year="2024", doi="10.1109/LSP.2024.3493801"),
 e("huang2023icip", P, "V", "Crossref and author PDF at EPFL (full text).",
   author="Huang, B. and Ebrahimi, T.", title="Event Data Stream Compression Based on Point Cloud Representation",
   booktitle="2023 IEEE International Conference on Image Processing (ICIP)", pages="3120--3124", year="2023", doi="10.1109/ICIP49359.2023.10222287"),
 e("wang2023jsen", A, "V-bib", "Crossref. Content second-hand.",
   author="Wang, C. and Wang, X. and Yan, C. and Ma, K.", title="Feature Representation and Compression Methods for Event-Based Data",
   journal="IEEE Sensors Journal", volume="23", number="5", pages="5109--5123", year="2023", doi="10.1109/JSEN.2023.3237754"),
 e("ding2024iscas", P, "V-bib", "Crossref. Content not read.",
   author="Ding, Z. and Wang, S. and Cai, Y. and Zeng, X. and Li, W. and Wang, M.", title="A Lossless Compression Algorithm with Hardware Implementation for Dynamic Vision Sensor",
   booktitle="2024 IEEE International Symposium on Circuits and Systems (ISCAS)", pages="1--5", year="2024", doi="10.1109/ISCAS58744.2024.10558375"),
 e("sezavar2024vcip", P, "V", "Crossref and arXiv (full text, Tables II and III).",
   author="Sezavar, A. and Brites, C. and Ascenso, J.", title="Learning-based Lossless Event Data Compression",
   booktitle="2024 IEEE International Conference on Visual Communications and Image Processing (VCIP)", pages="1--5", year="2024", doi="10.1109/VCIP63160.2024.10849853", eprint="2411.03010", archiveprefix="arXiv"),
 e("sezavar2024ism", P, "V", "Crossref and arXiv (full text, Tables III and IV).",
   author="Sezavar, A. and Brites, C. and Ascenso, J.", title="Low Complexity Learning-based Lossless Event-based Compression",
   booktitle="2024 IEEE International Symposium on Multimedia (ISM)", pages="85--92", year="2024", doi="10.1109/ISM63611.2024.00018", eprint="2411.07155", archiveprefix="arXiv"),
 e("sezavar2025spie", P, "V-bib", "Crossref and EPFL Infoscience record. Abstract only.",
   author="Sezavar, A. and Brites, C. and Ascenso, J. and Ebrahimi, T.", title="A learning-based lossless event data compression for computer vision applications",
   booktitle="Applications of Digital Image Processing XLVIII, Proc. SPIE", volume="13605", year="2025", doi="10.1117/12.3068095"),
 e("brites2025", A, "V", "Crossref and arXiv (about 100k of 121k characters read).",
   author="Brites, C. and Ascenso, J.", title="Neuromorphic Vision Data Coding: Classifying and Reviewing the Literature",
   journal="IEEE Access", volume="13", pages="14626--14657", year="2025", doi="10.1109/ACCESS.2025.3528375", eprint="2405.07050", archiveprefix="arXiv"),
 # ---- predictive
 e("stumpp2024", A, "V", "Crossref (re-checked for this brief). Technical details from the arXiv v1 full text.",
   author="Stumpp, Daniel C. and Akolkar, Himanshu and George, Alan D. and Benosman, Ryad B.", title="Flow-Based Visual Stream Compression for Event Cameras",
   journal="IEEE Internet of Things Journal", volume="11", number="24", pages="40229--40243", year="2024", doi="10.1109/JIOT.2024.3450428", eprint="2403.08086", archiveprefix="arXiv"),
 e("bairagi2022", T, "V", "University repository record and thesis PDF (full text, Tables 5.11 and 5.12 re-read for this brief). No DOI.",
   author="Bairagi, Arnob Kumar", title="Motion compensated compression for event-based cameras",
   school="University of Lethbridge", year="2022", url="https://hdl.handle.net/10133/6444"),
 e("delbruck2022csdvs", P, "V", "Crossref and arXiv 2202.13076 (full text).",
   author="Delbruck, T. and Li, C. and Graca, R. and McReynolds, B.", title="Utility and Feasibility of a Center Surround Event Camera",
   booktitle="2022 IEEE International Conference on Image Processing (ICIP)", pages="381--385", year="2022", doi="10.1109/ICIP46576.2022.9897354", eprint="2202.13076", archiveprefix="arXiv"),
 e("gallego2018cmax", P, "V", "CVF open-access page (abstract). No DOI on that page.",
   author="Gallego, G. and Rebecq, H. and Scaramuzza, D.", title="A Unifying Contrast Maximization Framework for Event Cameras, With Applications to Motion, Depth, and Optical Flow Estimation",
   booktitle="Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR)", pages="3867--3876", year="2018"),
 e("gallego2019focus", P, "V", "CVF open-access page (full text checked for any coding link). No DOI on that page.",
   author="Gallego, G. and Gehrig, M. and Scaramuzza, D.", title="Focus Is All You Need: Loss Functions for Event-Based Vision",
   booktitle="Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)", pages="12280--12289", year="2019"),
 e("shiba2022secrets", P, "V", "Crossref and arXiv 2207.10022 (abstract). Code repository fetched.",
   author="Shiba, S. and Aoki, Y. and Gallego, G.", title="Secrets of Event-Based Optical Flow",
   booktitle="Computer Vision -- ECCV 2022, Lecture Notes in Computer Science", pages="628--645", year="2022", doi="10.1007/978-3-031-19797-0_36", eprint="2207.10022", archiveprefix="arXiv"),
 # ---- lossy and metrics
 e("banerjee2021icip", P, "V", "Crossref and arXiv (ar5iv full text, comparison section cut off).",
   author="Banerjee, S. and Wang, Z. W. and Chopp, H. H. and Cossairt, O. and Katsaggelos, A. K.", title="Lossy Event Compression Based on Image-Derived Quad Trees and Poisson Disk Sampling",
   booktitle="2021 IEEE International Conference on Image Processing (ICIP)", pages="2154--2158", year="2021", doi="10.1109/ICIP42928.2021.9506546", eprint="2005.00974", archiveprefix="arXiv"),
 e("banerjee2024tnnls", A, "V", "Crossref (checked for this brief). Content from the arXiv preprint 2105.14164, which has a different title.",
   author="Banerjee, Srutarshi and Chopp, Henry H. and Zhang, Jianping and Wang, Zihao W. and Kang, Peng and Cossairt, Oliver and Katsaggelos, Aggelos", title="A Joint Intensity-Neuromorphic Event Imaging System With Bandwidth-Limited Communication Channel",
   journal="IEEE Transactions on Neural Networks and Learning Systems", volume="35", number="5", pages="7216--7230", year="2024", doi="10.1109/TNNLS.2022.3214779"),
 e("seleem2025access", A, "V", "Crossref and arXiv 2407.15531 (full text).",
   author="Seleem, Abdelrahman and Guarda, Andr{\\'e} F. R. and Rodrigues, Nuno M. M. and Pereira, Fernando", title="A Double Deep Learning-Based Solution for Efficient Event Data Coding and Classification",
   journal="IEEE Access", volume="13", pages="48703--48719", year="2025", doi="10.1109/ACCESS.2025.3551073", eprint="2407.15531", archiveprefix="arXiv"),
 e("seleem2026ojsp", A, "V", "Crossref (checked for this brief). Content from arXiv 2502.03285 v2.",
   author="Seleem, Abdelrahman and Guarda, Andr{\\'e} F. R. and Rodrigues, Nuno M. M. and Pereira, Fernando", title="Deep Learning-Based Event Data Coding: A Joint Spatiotemporal and Polarity Solution",
   journal="IEEE Open Journal of Signal Processing", volume="7", pages="222--237", year="2026", doi="10.1109/OJSP.2026.3656104", eprint="2502.03285", archiveprefix="arXiv"),
 e("rezaee2026", M, "V", "arXiv page (re-checked for this brief) and full text. Preprint.",
   author="Rezaee, Zahra and Brites, Catarina and Ascenso, Jo{\\~a}o", title="Lossy Event Compression: From Event Stream Distortion to Task Performance",
   year="2026", eprint="2608.28429", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2608.28429"),
 e("li2023astsm", A, "V-bib", "Crossref (checked for this brief). Content not read. Described through stumpp2024 and rezaee2026.",
   author="Li, Jianing and Fu, Yihua and Dong, Siwei and Yu, Zhaofei and Huang, Tiejun and Tian, Yonghong", title="Asynchronous Spatiotemporal Spike Metric for Event Cameras",
   journal="IEEE Transactions on Neural Networks and Learning Systems", volume="34", number="4", pages="1742--1753", year="2023", doi="10.1109/TNNLS.2021.3061122"),
 e("hamara2024", M, "V", "arXiv page and full text. Preprint, venue not stated.",
   author="Hamara, A. and Kilpatrick, B. and Baratta, A. and Kofink, B. and Freeman, A. C.", title="Low-Latency Scalable Streaming for Event-Based Vision",
   year="2024", eprint="2412.07889", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2412.07889"),
 e("araghi2025", P, "V", "CVF open-access page and arXiv 2505.21187 (full text). Code repository fetched.",
   author="Araghi, H. and van Gemert, J. and Tomen, N.", title="Making Every Event Count: Balancing Data Efficiency and Accuracy in Event Camera Subsampling",
   booktitle="Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="5044--5054", year="2025", eprint="2505.21187", archiveprefix="arXiv"),
 e("ogden2026", M, "V", "arXiv page (re-checked for this brief) and full text. Preprint.",
   author="Ogden, Ronald and Fridovich-Keil, David and Tanaka, Takashi", title="Rate-Distortion Analysis of Optically Passive Vision Compression",
   year="2026", eprint="2602.02768", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2602.02768"),
 e("khan2019bandwidth", A, "V", "MDPI page and publisher PDF (full text).",
   author="Khan, N. and Martini, M. G.", title="Bandwidth Modeling of Silicon Retinas for Next Generation Visual Sensor Networks",
   journal="Sensors", volume="19", number="8", pages="1751", year="2019", doi="10.3390/s19081751"),
 # ---- information theory
 e("miskowicz2006", A, "V", "MDPI page (full text).",
   author="Miskowicz, M.", title="Send-On-Delta Concept: An Event-Based Data Reporting Strategy",
   journal="Sensors", volume="6", number="1", pages="49--63", year="2006", doi="10.3390/s6010049"),
 e("mark1981", A, "V-bib", "Institutional record with abstract.",
   author="Mark, J. and Todd, T.", title="A Nonuniform Sampling Approach to Data Compression",
   journal="IEEE Transactions on Communications", volume="29", number="1", pages="24--32", year="1981", doi="10.1109/TCOM.1981.1094872"),
 e("guan2007ciss", P, "V-bib", "Institutional record with abstract.",
   author="Guan, K. M. and Singer, A. C.", title="Opportunistic Sampling of Bursty Signals by Level-Crossing: An Information Theoretical Approach",
   booktitle="2007 41st Annual Conference on Information Sciences and Systems (CISS)", pages="701--707", year="2007", doi="10.1109/CISS.2007.4298396"),
 e("guo2022wiener", A, "V", "Caltech repository record and arXiv 1909.01317 (abstract re-read for this brief).",
   author="Guo, Nian and Kostina, Victoria", title="Optimal Causal Rate-Constrained Sampling of the {W}iener Process",
   journal="IEEE Transactions on Automatic Control", volume="67", number="4", pages="1776--1791", year="2022", doi="10.1109/TAC.2021.3071953", eprint="1909.01317", archiveprefix="arXiv"),
 e("rubin1974", A, "V-bib", "Crossref. Formula not confirmed.",
   author="Rubin, I.", title="Information Rates and Data-Compression Schemes for {P}oisson Processes",
   journal="IEEE Transactions on Information Theory", volume="20", number="2", pages="200--210", year="1974", doi="10.1109/TIT.1974.1055195"),
 e("gallager1976", A, "V-bib", "Crossref. Formula not confirmed.",
   author="Gallager, R.", title="Basic Limits on Protocol Information in Data Communication Networks",
   journal="IEEE Transactions on Information Theory", volume="22", number="4", pages="385--398", year="1976", doi="10.1109/TIT.1976.1055588"),
 e("verdu1996", A, "V-bib", "Math-Net.Ru record (no DOI shown). The formula used here is as stated in coleman2008.",
   author="Verd{\\'u}, S.", title="The Exponential Distribution in Information Theory",
   journal="Problemy Peredachi Informatsii", volume="32", number="1", pages="100--111", year="1996",
   bibnote="English translation: Problems of Information Transmission, vol. 32, no. 1, pp. 86--95", url="https://www.mathnet.ru/eng/ppi324"),
 e("coleman2008", P, "V", "Institutional record and author PDF (full text, Theorem 3.1 re-read for this brief).",
   author="Coleman, T. P. and Kiyavash, N. and Subramanian, V. G.", title="The Rate-Distortion Function of a {P}oisson Process with a Queueing Distortion Measure",
   booktitle="2008 Data Compression Conference (DCC)", pages="63--72", year="2008", doi="10.1109/DCC.2008.92"),
 e("lapidoth2015", A, "V", "Crossref and arXiv 1102.3080 (abstract).",
   author="Lapidoth, A. and Mal{\\\"a}r, A. and Wang, L.", title="Covering Point Patterns",
   journal="IEEE Transactions on Information Theory", volume="61", number="9", pages="4521--4533", year="2015", doi="10.1109/TIT.2015.2453946", eprint="1102.3080", archiveprefix="arXiv"),
 e("shen2021itw", P, "V", "Crossref and author-hosted PDF.",
   author="Shen, H.-A. and Moser, S. M. and Pfister, J.-P.", title="Rate-Distortion Problems of the {P}oisson Process: a Group-Theoretic Approach",
   booktitle="2021 IEEE Information Theory Workshop (ITW)", pages="1--6", year="2021", doi="10.1109/ITW48936.2021.9611405"),
 e("shende2022", M, "V", "arXiv page (re-checked for this brief) and PDF. Preprint, journal version not confirmed.",
   author="Shende, Nirmal V. and Wagner, Aaron B.", title="Functional Covering of Point Processes",
   year="2022", eprint="2204.09188", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2204.09188"),
 e("mcfadden1965", A, "V-bib", "Crossref. Content as quoted in coleman2008.",
   author="McFadden, J. A.", title="The Entropy of a Point Process",
   journal="Journal of the Society for Industrial and Applied Mathematics", volume="13", number="4", pages="988--994", year="1965", doi="10.1137/0113066"),
 e("papangelou1978", A, "V-bib", "Springer page. Abstract not available. Content from general knowledge of the result.",
   author="Papangelou, F.", title="On the Entropy Rate of Stationary Point Processes and Its Discrete Approximation",
   journal="Zeitschrift f{\\\"u}r Wahrscheinlichkeitstheorie und Verwandte Gebiete", volume="44", number="3", pages="191--211", year="1978", doi="10.1007/BF00534210"),
 e("daley2004", A, "V", "Cambridge page (abstract).",
   author="Daley, D. J. and Vere-Jones, D.", title="Scoring Probability Forecasts for Point Processes: the Entropy Score and Information Gain",
   journal="Journal of Applied Probability", volume="41", number="A", pages="297--312", year="2004", doi="10.1239/jap/1082552206"),
 e("koliander2018", A, "V-bib", "DOI record and arXiv 1704.05758. Abstract level.",
   author="Koliander, G. and Schuhmacher, D. and Hlawatsch, F.", title="Rate-Distortion Theory of Finite Point Processes",
   journal="IEEE Transactions on Information Theory", volume="64", number="8", pages="5832--5861", year="2018", doi="10.1109/TIT.2018.2829161", eprint="1704.05758", archiveprefix="arXiv"),
 e("strong1998", A, "V-bib", "Crossref. Content from general knowledge of the method.",
   author="Strong, S. P. and Koberle, R. and de Ruyter van Steveninck, R. R. and Bialek, W.", title="Entropy and Information in Neural Spike Trains",
   journal="Physical Review Letters", volume="80", number="1", pages="197--200", year="1998", doi="10.1103/PhysRevLett.80.197"),
 e("paninski2003", A, "V-bib", "Crossref. Content from general knowledge of the method.",
   author="Paninski, L.", title="Estimation of Entropy and Mutual Information",
   journal="Neural Computation", volume="15", number="6", pages="1191--1253", year="2003", doi="10.1162/089976603321780272"),
 e("kennel2005", A, "V-bib", "Crossref. Content from general knowledge of the method.",
   author="Kennel, M. B. and Shlens, J. and Abarbanel, H. D. I. and Chichilnisky, E. J.", title="Estimating Entropy Rates with {B}ayesian Confidence Intervals",
   journal="Neural Computation", volume="17", number="7", pages="1531--1576", year="2005", doi="10.1162/0899766053723050"),
 # ---- generative models
 e("lichtsteiner2008", A, "V-bib", "Crossref. Full text not read.",
   author="Lichtsteiner, P. and Posch, C. and Delbruck, T.", title="A 128$\\times$128 120 {dB} 15 $\\mu$s Latency Asynchronous Temporal Contrast Vision Sensor",
   journal="IEEE Journal of Solid-State Circuits", volume="43", number="2", pages="566--576", year="2008", doi="10.1109/JSSC.2007.914337"),
 e("gallego2022survey", A, "V", "Crossref and arXiv 1904.08405 (full text).",
   author="Gallego, G. and Delbruck, T. and Orchard, G. and Bartolozzi, C. and Taba, B. and Censi, A. and Leutenegger, S. and Davison, A. J. and Conradt, J. and Daniilidis, K. and Scaramuzza, D.", title="Event-Based Vision: A Survey",
   journal="IEEE Transactions on Pattern Analysis and Machine Intelligence", volume="44", number="1", pages="154--180", year="2022", doi="10.1109/TPAMI.2020.3008413", eprint="1904.08405", archiveprefix="arXiv"),
 e("hu2021v2e", P, "V", "Crossref and arXiv 2006.07722 (full text). Code repository fetched.",
   author="Hu, Y. and Liu, S.-C. and Delbruck, T.", title="v2e: From Video Frames to Realistic {DVS} Events",
   booktitle="2021 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="1312--1321", year="2021", doi="10.1109/CVPRW53098.2021.00144", eprint="2006.07722", archiveprefix="arXiv"),
 e("lin2022voltmeter", P, "V", "Crossref and ECVA PDF (full text). Code repository fetched.",
   author="Lin, S. and Ma, Y. and Guo, Z. and Wen, B.", title="{DVS-Voltmeter}: Stochastic Process-Based Event Simulator for Dynamic Vision Sensors",
   booktitle="Computer Vision -- ECCV 2022, Lecture Notes in Computer Science", pages="578--593", year="2022", doi="10.1007/978-3-031-20071-7_34"),
 e("gu2021stppp", P, "V", "Crossref, CVF page, and arXiv 2106.06887 (full text). Pages follow the IEEE record of this DOI. The CVF open-access version is paginated 13495-13504. Code repository fetched.",
   author="Gu, C. and Learned-Miller, E. and Sheldon, D. and Gallego, G. and Bideau, P.", title="The Spatio-Temporal {P}oisson Point Process: A Simple Model for the Alignment of Event Camera Data",
   booktitle="Proc. IEEE/CVF International Conference on Computer Vision (ICCV)", pages="13475--13484", year="2021", doi="10.1109/ICCV48922.2021.01324", eprint="2106.06887", archiveprefix="arXiv"),
 e("hashimoto2026", M, "V", "arXiv page and PDF. Preprint.",
   author="Hashimoto, K. and Serizawa, K. and Kishida, M.", title="Receding-Horizon Maximum-Likelihood Estimation of Neural-{ODE} Dynamics and Thresholds from Event Cameras",
   year="2026", eprint="2603.05011", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2603.05011"),
 e("baldwin2020", P, "V", "CVF page and arXiv 2003.08282 (full text). DOI not confirmed.",
   author="Baldwin, R. W. and Almatrafi, M. and Asari, V. and Hirakawa, K.", title="Event Probability Mask ({EPM}) and Event Denoising Convolutional Neural Network ({EDnCNN}) for Neuromorphic Cameras",
   booktitle="Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)", pages="1701--1710", year="2020", eprint="2003.08282", archiveprefix="arXiv"),
 e("joubert2021", A, "V", "Crossref and Frontiers full text. Code repository fetched.",
   author="Joubert, D. and Marcireau, A. and Ralph, N. and Jolley, A. and van Schaik, A. and Cohen, G.", title="Event Camera Simulator Improvements via Characterized Parameters",
   journal="Frontiers in Neuroscience", volume="15", pages="702765", year="2021", doi="10.3389/fnins.2021.702765"),
 e("graca2025model", M, "V", "arXiv page and PDF. Workshop DOI not confirmed.",
   author="Graca, R. and Delbruck, T.", title="Towards a Physically Realistic Computationally Efficient {DVS} Pixel Model",
   year="2025", eprint="2505.07386", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2505.07386"),
 # ---- noise
 e("guo2023denoise", A, "V-bib", "Crossref. Full text not read.",
   author="Guo, S. and Delbruck, T.", title="Low Cost and Latency Event Camera Background Activity Denoising",
   journal="IEEE Transactions on Pattern Analysis and Machine Intelligence", volume="45", number="1", pages="785--795", year="2023", doi="10.1109/TPAMI.2022.3152999"),
 e("riosnavarro2023", P, "V", "DOI metadata and arXiv 2304.07543 (full text).",
   author="Rios-Navarro, A. and Guo, S. and Abarajithan, G. and Vijayakumar, K. and Linares-Barranco, A. and Aarrestad, T. and Kastner, R. and Delbruck, T.", title="Within-Camera Multilayer Perceptron {DVS} Denoising",
   booktitle="2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="3933--3942", year="2023", doi="10.1109/CVPRW59228.2023.00409", eprint="2304.07543", archiveprefix="arXiv"),
 e("mcreynolds2023pairs", M, "V", "arXiv page (re-checked for this brief) and PDF. The 90% figure is from the full text (Sec. III), not the abstract.",
   author="McReynolds, Brian and Graca, Rui and Delbruck, Tobi", title="Exploiting Alternating {DVS} Shot Noise Event Pair Statistics to Reduce Background Activity",
   year="2023", eprint="2304.03494", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2304.03494"),
 e("graca2023tutorial", P, "V", "Crossref and CVF PDF (full text).",
   author="Graca, R. and McReynolds, B. and Delbruck, T.", title="Shining Light on the {DVS} Pixel: A Tutorial and Discussion about Biasing and Optimization",
   booktitle="2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="4045--4053", year="2023", doi="10.1109/CVPRW59228.2023.00423"),
 e("graca2023limits", P, "V", "IISS page and arXiv 2304.04019 (full text).",
   author="Graca, R. and McReynolds, B. and Delbruck, T.", title="Optimal Biasing and Physical Limits of {DVS} Event Noise",
   booktitle="2023 International Image Sensor Workshop (IISW)", year="2023", doi="10.60928/dlpf-irjd", eprint="2304.04019", archiveprefix="arXiv"),
 e("cao2025noise2image", A, "V", "arXiv 2404.01298 (authors, DOI, full text) and DOI metadata. End page not confirmed.",
   author="Cao, R. and Galor, D. and Kohli, A. and Yates, J. L. and Waller, L.", title="{Noise2Image}: Noise-Enabled Static Scene Recovery for Event Cameras",
   journal="Optica", volume="12", number="1", pages="46", year="2025", doi="10.1364/OPTICA.538916", eprint="2404.01298", archiveprefix="arXiv"),
 e("mcreynolds2025amos", P, "V", "Conference PDF. No DOI exists.",
   author="McReynolds, B. and Oliver, R. and McMahon-Crabtree, P. and Zolnowski, M. and Delbruck, T.", title="Bias and Denoising Techniques to Improve Dim {RSO} Detection by up to 2.9x with an Event-based Vision Sensor",
   booktitle="Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS)", year="2025",
   url="https://amostech.com/TechnicalPapers/2025/SDA_Systems-and-Instrumentation/McReynolds1.pdf"),
 e("mcreynolds2024scurve", M, "V", "arXiv page and PDF. Venue not confirmed.",
   author="McReynolds, B. and Graca, R. and Kulesza, L. and McMahon-Crabtree, P.", title="Re-Interpreting the Step-Response Probability Curve to Extract Fundamental Physical Parameters of Event-based Vision Sensors",
   year="2024", eprint="2404.07656", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2404.07656"),
 e("oliver2025", A, "V", "Springer open-access page (full text).",
   author="Oliver, R. and McReynolds, B. and Savransky, D.", title="Event-Based Sensor Noise Modeling for Space-Based Space Domain Awareness",
   journal="The Journal of the Astronautical Sciences", volume="72", number="5", pages="46", year="2025", doi="10.1007/s40295-025-00523-5"),
 e("zhao2025date", P, "V", "Crossref and author PDF.",
   author="Zhao, Q. and Ji, Y. and Wang, J. and Wu, J. and Shi, G.", title="Simultaneous Denoising and Compression for {DVS} with Partitioned Cache-Like Spatiotemporal Filter",
   booktitle="2025 Design, Automation and Test in Europe Conference (DATE)", pages="1--7", year="2025", doi="10.23919/DATE64628.2025.10992696"),
 e("shiba2025noise", M, "V", "arXiv page (lists ICCV 2025) and full text. Proceedings pages not confirmed.",
   author="Shiba, S. and Aoki, Y. and Gallego, G.", title="Simultaneous Motion And Noise Estimation with Event Cameras",
   year="2025", eprint="2504.04029", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2504.04029, ICCV 2025"),
 # ---- spike / time encoding
 e("lazar2004", A, "V-bib", "Crossref. Full text not read.",
   author="Lazar, A. A. and Toth, L. T.", title="Perfect Recovery and Sensitivity Analysis of Time Encoded Bandlimited Signals",
   journal="IEEE Transactions on Circuits and Systems I: Regular Papers", volume="51", number="10", pages="2060--2073", year="2004", doi="10.1109/TCSI.2004.835026"),
 e("martineznuevo2019", A, "V", "arXiv 1802.04672 and DOI metadata (abstract).",
   author="Mart{\\'i}nez-Nuevo, P. and Lai, H.-Y. and Oppenheim, A. V.", title="Delta-Ramp Encoder for Amplitude Sampling and Its Interpretation as Time Encoding",
   journal="IEEE Transactions on Signal Processing", volume="67", number="10", pages="2516--2527", year="2019", doi="10.1109/TSP.2019.2904027", eprint="1802.04672", archiveprefix="arXiv"),
 e("adam2022", A, "V", "arXiv 2104.14511 and DOI metadata (abstract).",
   author="Adam, K. and Scholefield, A. and Vetterli, M.", title="Asynchrony Increases Efficiency: Time Encoding of Videos and Low-Rank Signals",
   journal="IEEE Transactions on Signal Processing", volume="70", pages="105--116", year="2022", doi="10.1109/TSP.2021.3133709", eprint="2104.14511", archiveprefix="arXiv"),
 e("adam2022events", M, "V", "arXiv page and PDF. Preprint, venue not confirmed.",
   author="Adam, K. and Scholefield, A. and Vetterli, M.", title="How Asynchronous Events Encode Video",
   year="2022", eprint="2206.04341", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2206.04341"),
 e("naaman2021quant", M, "V", "arXiv page and v2 PDF. Journal version not confirmed.",
   author="Naaman, H. and Bernardo, N. I. and Cohen, A. and Eldar, Y. C.", title="Time Encoding Quantization of Bandlimited and Finite-Rate-of-Innovation Signals",
   year="2021", eprint="2110.01928", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2110.01928"),
 e("boahen2000", A, "V-bib", "DOI metadata. Content not read.",
   author="Boahen, K. A.", title="Point-to-Point Connectivity Between Neuromorphic Chips Using Address Events",
   journal="IEEE Transactions on Circuits and Systems II: Analog and Digital Signal Processing", volume="47", number="5", pages="416--434", year="2000", doi="10.1109/82.842110"),
 e("chen2023tccn", A, "V", "arXiv 2206.06047 and DOI metadata (abstract).",
   author="Chen, J. and Skatchkovsky, N. and Simeone, O.", title="Neuromorphic Wireless Cognition: Event-Driven Semantic Communications for Remote Inference",
   journal="IEEE Transactions on Cognitive Communications and Networking", volume="9", number="2", pages="252--265", year="2023", doi="10.1109/TCCN.2023.3236940", eprint="2206.06047", archiveprefix="arXiv"),
 e("ke2024dib", M, "V", "arXiv page (abstract). Preprint.",
   author="Ke, Y. and Utkovski, Z. and Heshmati, M. and Simeone, O. and Dommel, J. and Stanczak, S.", title="Neuromorphic Wireless Device-Edge Co-Inference via the Directed Information Bottleneck",
   year="2024", eprint="2404.01804", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2404.01804"),
 # ---- datasets
 e("verma2024etram", P, "V", "CVF page, arXiv 2403.19976 (re-checked for this brief), project site, and dataset documentation. No DOI on the CVF page.",
   author="Verma, Aayush Atul and Chakravarthi, Bharatesh and Vaghela, Arpitsinh and Wei, Hua and Yang, Yezhou", title="{eTraM}: Event-based Traffic Monitoring Dataset",
   booktitle="Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)", pages="22637--22646", year="2024", eprint="2403.19976", archiveprefix="arXiv"),
 e("gehrig2021dsec", A, "V", "arXiv 2103.06011, DOI metadata, dataset site (full text).",
   author="Gehrig, M. and Aarents, W. and Gehrig, D. and Scaramuzza, D.", title="{DSEC}: A Stereo Event Camera Dataset for Driving Scenarios",
   journal="IEEE Robotics and Automation Letters", volume="6", number="3", pages="4947--4954", year="2021", doi="10.1109/LRA.2021.3068942", eprint="2103.06011", archiveprefix="arXiv"),
 e("detournemire2020", M, "V", "arXiv page and PDF, dataset page.",
   author="de Tournemire, P. and Nitti, D. and Perot, E. and Migliore, D. and Sironi, A.", title="A Large Scale Event-based Detection Dataset for Automotive",
   year="2020", eprint="2001.08499", archiveprefix="arXiv", howpublished="arXiv preprint arXiv:2001.08499"),
 e("perot2020", P, "V", "NeurIPS proceedings page and arXiv 2009.13436 (full text). No DOI.",
   author="Perot, E. and de Tournemire, P. and Nitti, D. and Masci, J. and Sironi, A.", title="Learning to Detect Objects with a 1 Megapixel Event Camera",
   booktitle="Advances in Neural Information Processing Systems 33 (NeurIPS 2020)", pages="16639--16652", year="2020", eprint="2009.13436", archiveprefix="arXiv"),
 e("mueggler2017", A, "V", "arXiv 1610.08336, DOI metadata, dataset page (full text).",
   author="Mueggler, E. and Rebecq, H. and Gallego, G. and Delbruck, T. and Scaramuzza, D.", title="The Event-Camera Dataset and Simulator: Event-based Data for Pose Estimation, Visual Odometry, and {SLAM}",
   journal="The International Journal of Robotics Research", volume="36", number="2", pages="142--149", year="2017", doi="10.1177/0278364917691115", eprint="1610.08336", archiveprefix="arXiv"),
 e("chaney2023m3ed", P, "V", "CVF page and PDF, dataset site. DOI not confirmed.",
   author="Chaney, K. and Cladera, F. and Wang, Z. and Bisulco, A. and Hsieh, M. A. and Korpela, C. and Kumar, V. and Taylor, C. J. and Daniilidis, K.", title="{M3ED}: Multi-Robot, Multi-Sensor, Multi-Environment Event Dataset",
   booktitle="Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)", pages="4016--4023", year="2023"),
 e("zhu2018mvsec", A, "V", "arXiv 1801.10202, DOI metadata, dataset site.",
   author="Zhu, A. Z. and Thakur, D. and {\\\"O}zaslan, T. and Pfrommer, B. and Kumar, V. and Daniilidis, K.", title="The Multivehicle Stereo Event Camera Dataset: An Event Camera Dataset for {3D} Perception",
   journal="IEEE Robotics and Automation Letters", volume="3", number="3", pages="2032--2039", year="2018", doi="10.1109/LRA.2018.2800793", eprint="1801.10202", archiveprefix="arXiv"),
 # ---- web sources
 e("jpegxe2026press", M, "V", "Web page fetched October 8, 2026 (re-read for this brief).",
   author="{JPEG Committee}", title="112th Meeting -- Leiria, Portugal -- {JPEG XE} becomes an International Standard",
   year="2026", howpublished="Press release, October 7, 2026", url="https://jpeg.org/items/20261007_press.html"),
 e("prophesee_evt", M, "V", "Two vendor documentation pages fetched October 8, 2026 (EVT 3.0 at the URL given, EVT 2.0 at .../encoding_formats/evt2.html).",
   author="{Prophesee}", title="{EVT} 3.0 Format and {EVT} 2.0 Format, Metavision {SDK} Docs 5.3.1",
   year="2026", howpublished="Online documentation", bibnote="EVT 2.0 page: https://docs.prophesee.ai/stable/data/encoding_formats/evt2.html", url="https://docs.prophesee.ai/stable/data/encoding_formats/evt3.html"),
 e("prophesee_esp", M, "V", "Vendor documentation page fetched October 8, 2026.",
   author="{Prophesee}", title="Metavision {SDK} Documentation: Event Signal Processing",
   year="2026", howpublished="Online documentation", url="https://docs.prophesee.ai/stable/hw/manuals/esp.html"),
 e("prophesee_ecf", M, "V", "Repository and codec source fetched October 8, 2026.",
   author="{Prophesee}", title="{HDF5Plugin-ECF}",
   year="2026", howpublished="Software repository", url="https://github.com/prophesee-ai/hdf5_ecf"),
 e("dsec_format", M, "V", "Dataset documentation page fetched October 8, 2026.",
   author="{Robotics and Perception Group, University of Zurich}", title="{DSEC} Data Format",
   year="2026", howpublished="Online documentation", url="https://dsec.ifi.uzh.ch/data-format/"),
]

UNVERIFIED = [
 "A. S. Bedekar, \"On the information about message arrival times required for in-order decoding,\" Proc. IEEE ISIT, p. 227. Year not confirmed (printed with a typo in coleman2008). Not used for any number.",
 "T. Finateu et al., \"A 1280x720 Back-Illuminated Stacked Temporal Contrast Event-Based Vision Sensor with 4.86 um Pixels, 1.066 GEPS Readout, Programmable Event-Rate Controller and Compressive Data-Formatting Pipeline,\" ISSCC 2020. Seen only on an index page. DOI not confirmed (a Crossref title query returned unrelated records).",
 "B. Huang, D. Lazzarotto, T. Ebrahimi, \"Evaluation of the impact of lossy compression on event camera-based computer vision tasks,\" Proc. SPIE 12674, 2023. Publisher page not reachable. DOI 10.1117/12.2676419 seen only on the EPFL repository record.",
 "M. Martini et al., \"Comparison of point-cloud construction strategies for the lossless compression of event camera data,\" TechRxiv, 2025, DOI 10.36227/techrxiv.174535660.05715604/v1. Bibliographic record seen in Crossref. Content not accessible.",
 "A. Junco de Haas, \"Event Camera Lossless Compression for Satellite Applications,\" Master's thesis, TU Munich. Year unclear (2024 or 2025), no DOI.",
 "Hasssan et al., 2022, low-precision sparse autoencoder for DVS compression. Known only through brites2025. Title, authors, and venue not confirmed.",
 "G. Cohen et al., \"Spatial and Temporal Downsampling in Event-Based Visual Classification,\" IEEE TNNLS, 2018. Seen only on a university portal.",
 "JPEG XE Common Test Conditions (WG1 N100827, N100891, N101324) and Call for Proposals (N100888). Listed on jpeg.org. The documents could not be opened, so the anchor list (lz4, bzip2, 7z) is second-hand.",
 "Inter-cube prediction result of dong2019 (CR 2.64 vs 2.65 on DDD17). Second-hand from brites2025. The primary full text was not obtained.",
 "Entropy values in Fig. 9 of khan2020. Only the surrounding text was readable.",
 "Rate and noise statements about the IMX636 readout (timestamp granularity, event rate controller behavior under load). Not found in a primary source. Treated as an open check in Section 5.",
]

def bib(en):
    f = en["f"]; out = ["@%s{%s," % (en["typ"], en["key"])]
    order = ["author","title","journal","booktitle","school","volume","number","pages","year","doi","eprint","archiveprefix","howpublished","note","url"]
    for k in order:
        kk = "bibnote" if k == "note" else k
        if kk in f:
            out.append("  %s = {%s}," % (k, f[kk]))
    out.append("}")
    return "\n".join(out)

def plain(s):
    s = s.replace('{\\"a}', "a").replace("{\\'i}", "i").replace("{\\'e}", "e").replace("{\\'u}", "u").replace("{\\~a}", "a").replace('{\\"u}', "u").replace('{\\"O}', "O")
    s = s.replace("$\\times$", "x").replace("$\\mu$", "u").replace("--", "-")
    return re.sub(r"[{}]", "", s)

def authors_plain(a):
    if a.startswith("{") and a.endswith("}"):
        return plain(a)
    names = []
    for n in a.split(" and "):
        n = plain(n)
        if "," in n:
            fam, giv = [x.strip() for x in n.split(",", 1)]
            names.append("%s %s" % (giv, fam))
        else:
            names.append(n)
    return ", ".join(names)

def line(en):
    f = en["f"]; parts = [authors_plain(f["author"]) + ",", '"%s,"' % plain(f["title"])]
    venue = f.get("journal") or f.get("booktitle") or f.get("school") or f.get("howpublished") or ""
    v = plain(venue)
    if "volume" in f: v += ", vol. %s" % f["volume"]
    if "number" in f: v += ", no. %s" % f["number"]
    if "pages" in f: v += ", pp. %s" % plain(f["pages"]) if "--" in f["pages"] else ", art. %s" % f["pages"]
    v += ", %s." % f["year"]
    parts.append(v)
    ids = []
    if "doi" in f: ids.append("DOI %s." % f["doi"])
    if "eprint" in f and "arXiv" not in v: ids.append("arXiv:%s." % f["eprint"])
    if "url" in f: ids.append(f["url"])
    return "- **[%s]** %s %s **%s.** %s" % (en["key"], " ".join(parts), " ".join(ids), en["status"], en["note"])

if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent.parent
    keys = [en["key"] for en in ENTRIES]
    assert len(keys) == len(set(keys)), "duplicate keys"
    header = ("% references.bib for event_coding_brief.md\n"
              "% Only entries whose bibliographic fields were confirmed on a primary page are included.\n"
              "% Author given names are abbreviated where only initials were confirmed.\n"
              "% Generated by tools/make_refs.py on 2026-10-08.\n\n")
    (root / "references.bib").write_text(header + "\n\n".join(bib(en) for en in ENTRIES) + "\n")
    ref_md = "\n".join(line(en) for en in ENTRIES)
    ref_md += "\n\n### Not verified (not in `references.bib`)\n\n" + "\n".join("- **U.** " + u for u in UNVERIFIED)
    brief = root / "event_coding_brief.md"
    txt = brief.read_text()
    start = txt.index("PLACEHOLDER_REFERENCES") if "PLACEHOLDER_REFERENCES" in txt else None
    if start is None:
        a = txt.index("<!-- REFS-BEGIN -->"); b = txt.index("<!-- REFS-END -->")
        txt = txt[:a] + "<!-- REFS-BEGIN -->\n" + ref_md + "\n" + txt[b:]
    else:
        txt = txt.replace("PLACEHOLDER_REFERENCES", "<!-- REFS-BEGIN -->\n" + ref_md + "\n<!-- REFS-END -->")
    brief.write_text(txt)
    # consistency: every cited key exists, every entry is cited
    cited = set()
    for grp in re.findall(r"\[([a-z0-9_, ]+)\]", txt.split("<!-- REFS-BEGIN -->")[0]):
        for k in grp.split(","):
            k = k.strip()
            if re.fullmatch(r"[a-z]+[a-z0-9_]*\d{4}[a-z0-9_]*|prophesee_[a-z]+|dsec_format|jpegxe2026press", k):
                cited.add(k)
    print("entries:", len(keys), "cited:", len(cited))
    print("cited but missing:", sorted(cited - set(keys)))
    print("in bib but not cited:", sorted(set(keys) - cited))
