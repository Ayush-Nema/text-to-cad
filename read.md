# Generative Geometric Intelligence: A Comprehensive Analysis of Open Source Repositories for Natural Language to CAD Conversion

- **STL** stands for *Stereolithography* (or *Standard Triangle/Tessellation Language*) and represents a model as a
  mesh of triangles, ideal for 3D printing
- **STEP** stands for _Standard for the Exchange of Product data_ and is a precise, universal format for sharing CAD
  designs between different software, retaining full geometry and product information, not just surface data.

---

## 1. Introduction: The Geometric Singularity

The intersection of Large Language Models (LLMs) and Computer-Aided Design (CAD) represents a transformative moment in
engineering and manufacturing. For decades, the translation of human intent into physical specification has been
mediated by complex Graphical User Interfaces (GUIs) and steep learning curves. The query to identify open-source Git
repositories capable of converting natural language text into CAD designs—specifically targeting the disparate formats
of STL (Stereolithography) and STEP (Standard for the Exchange of Product model data)—exposes a fundamental bifurcation
in the current technological landscape. This schism exists between the probabilistic generation of visual meshes and the
deterministic construction of parametric geometry.

The challenge of generating "CAD" is not monolithic. It comprises two distinct mathematical objectives: the generation
of surface topology for visualization and 3D printing (Mesh/STL), and the generation of volumetric logic for precision
manufacturing (B-Rep/STEP). While recent advancements in latent diffusion have solved the former to a degree of artistic
satisfaction, the latter remains a frontier of intense academic and open-source development, requiring models to "
reason" about constraints, dimensions, and assembly hierarchy rather than simply "dreaming" shapes.

This report provides an exhaustive, expert-level analysis of the open-source ecosystem as it stands in mid-2025. It
dissects the architectures, capabilities, and limitations of over a dozen key repositories, ranging from code-generating
LLM frameworks like **Text-to-CadQuery** and **PartCAD**, to sequence-prediction models like **Text2CAD** and **Seek-CAD
**, and finally to the visual mesh generators like **Hunyuan3D-2** and **Shap-E**. Furthermore, it addresses the
critical interoperability gap—the conversion of AI-generated meshes into usable STEP files—by analyzing utility
repositories and scripting methodologies that bridge this divide.

### 1.1. The Representation Gap: Mesh vs. Boundary Representation

To understand the efficacy of the repositories identified, one must first ground the analysis in the data structures
they manipulate. The user's request for both STL and STEP files necessitates a dual-track analysis, as these formats
imply fundamentally different generative approaches.

**STL (Stereolithography)** is a discretized representation of 3D geometry. It describes a surface as a collection of
unstructured triangular facets. A model generating STL files functions similarly to a 2D image generator: it predicts
the occupancy of space (voxels) or the location of surface points. This approach is computationally forgiving but
mathematically "dumb." An STL cylinder is not a cylinder; it is thousands of tiny flat triangles approximating a curve.
It has no radius parameter, no axis definition, and no history.

**STEP (ISO 10303)** utilizes Boundary Representation (B-Rep). It describes geometry analytically using NURBS (
Non-Uniform Rational B-Splines). A STEP cylinder is a mathematical definition: a circle of radius $r$ extruded along
vector $v$. Generating a STEP file requires the AI to understand the _logic_ of construction. It is a linguistic and
logical task, not merely a visual one. Consequently, the most successful open-source repositories for STEP generation do
not output geometry directly; they output _code_ (Python, OpenSCAD) which is then compiled by a geometric kernel into
the final B-Rep.

The following analysis categorizes open-source efforts into three primary paradigms based on this distinction:

1. **The Code-Centric Paradigm:** LLMs that generate scripts (CadQuery, Build123d, OpenSCAD) to produce parametric
   STEP/STL files.
2. **The Sequence-Prediction Paradigm:** Models that predict construction sequences or geometric tokens directly.
3. **The Latent Diffusion Paradigm:** Models that generate visual meshes (STL/GLB) via denoising, prioritizing
   aesthetics over engineering precision.

---

## 2. The Code-Centric Paradigm: Parametric Precision

The most robust route to generating high-fidelity, manufacturing-ready CAD (STEP) from natural language is through *
*Program Synthesis**. By treating CAD design as a coding problem, developers leverage the advanced reasoning
capabilities of LLMs trained on Python and C++. The following repositories represent the vanguard of this approach.

### 2.1. Text-to-CadQuery: The Academic Standard

Repository: Text-to-CadQuery/Text-to-CadQuery
Primary Output: Python Scripts (CadQuery) $\rightarrow$ STEP/STL
Key Innovation: LoRA Fine-tuning on Augmented Datasets

The **Text-to-CadQuery** project, originating from research at Arizona State University, addresses the primary failure
mode of generic LLMs in CAD: syntax hallucination.1 While models like GPT-4 or Llama 3 understand Python generally, they
often lack knowledge of the specific, functional API of libraries like **CadQuery**.

#### 2.1.1. Dataset and Methodology

The core contribution of this repository is the curation of a massive domain-specific dataset. The authors augmented the
existing **Text2CAD** dataset (originally sequence-based) with over 170,000 CadQuery code annotations.2 This
transformation converts the abstract geometric intent of the original dataset into executable logic.

The methodology employs **Low-Rank Adaptation (LoRA)** to fine-tune open-source base models (including Llama 3, Mistral,
and CodeLlama) specifically for the CadQuery syntax. This approach yields a dramatic improvement in "Pass@1" rates—the
probability that the code generated by the model will execute without errors and produce the correct shape. The research
indicates an improvement in exact match accuracy from ~58% (base models) to ~69% (fine-tuned).3

#### 2.1.2. Architecture and Usage

The repository provides the training scripts, the augmented dataset, and links to the model weights hosted on Hugging
Face.

- **Input:** A text description (e.g., "A rectangular base 10x10 with a center hole of radius 2").
- **Process:** The fine-tuned LLM predicts the sequence of CadQuery function
  calls: `cq.Workplane("XY").box(10, 10, 1).faces(">Z").hole(2)`.
- **Output:** The system executes this script using the CadQuery interpreter.
- **Export:** Because CadQuery sits on top of the **OpenCASCADE** kernel, the resulting object has infinite precision.
  The script can explicitly call `exporters.export(result, 'model.step')` or `exporters.export(result, 'model.stl')`.3

#### 2.1.3. Evaluation for User Needs

This repository is arguably the most direct answer to the user's request for a system that handles both STL and STEP
via "open source." It is not merely a wrapper for an API but a fundamental contribution to open-source model weights.
Users can download the weights and run them locally, ensuring data privacy and independence from cloud services. The
reliance on Python ensures that the output is not just a "dead" file but an editable, parametric script.1

### 2.2. PartCAD: The Infrastructure of Generative Design

Repository: openvmp/partcad
Primary Output: STEP, STL, 3MF, OBJ
Key Innovation: AI-Augmented Package Management

While Text-to-CadQuery focuses on the _model_, **PartCAD** focuses on the _workflow_. It is an open-source package
manager for CAD models, designed to treat physical parts with the same version control and dependency logic as software
libraries.4

#### 2.2.1. AI-Driven Component Definition

PartCAD has integrated Generative AI directly into its configuration syntax. Instead of manually writing a script, a
user can define a part in the `partcad.yaml` file using a descriptive block:

```yaml
parts:
  gears/spur_gear:
    type: ai-cadquery
    desc: "A spur gear with 20 teeth, module 1, and a 5mm bore."
```

Upon build, PartCAD interfaces with an LLM provider—supporting both cloud APIs (OpenAI, Google) and **local inference
via Ollama**—to generate the implementation script.6 This is a crucial feature for the "open source" requirement, as it
allows the user to plug in completely open weights (like **DeepSeek-Coder-V2** or **CodeLlama**) to drive the generation
process.

#### 2.2.2. Kernel Agnosticism and Export

A significant advantage of PartCAD is its neutrality regarding geometric kernels. It supports generating scripts for *
*OpenSCAD**, **CadQuery**, and **Build123d**.7

- **Build123d Support:** This is particularly noteworthy. Build123d is a newer, more "Pythonic" library than CadQuery,
  and recent anecdotal evidence suggests that LLMs may find its syntax more intuitive to generate due to its explicit
  context managers.8
- **Output versatility:** The `pc render` command automates the pipeline, executing the generated script and producing
  artifacts in all requested formats, including **STEP** (for MCAD) and **STL** (for slicing). This satisfies the user's
  requirement for multiple output formats within a single, unified toolchain.7

### 2.3. C3D: The Local CLI Workhorse

Repository: unxversal/c3d
Primary Output: STL (Managed), STEP (Script-supported)
Key Innovation: Local-First Architecture via Ollama

**C3D** (Compute 3D) represents the developer-centric implementation of text-to-CAD. It is a Command Line Interface (
CLI) tool designed specifically to lower the barrier to entry for generating 3D models locally.11

#### 2.3.1. Integration with Local Inference

Unlike web-based tools that act as wrappers for proprietary APIs, C3D is architected to work with **Ollama**. The
repository facilitates the downloading of a specific fine-tuned model (`joshuaokolo/C3Dv0`), which is based on the
Google Gemma architecture.11 This model has been trained on a subset of the Text-to-CadQuery dataset, optimized for
consumer hardware with quantization (GGUF format).

#### 2.3.2. Workflow and Limitations

The C3D workflow is interactive. The user inputs a prompt via the CLI, and the model generates a Python script. The tool
includes a `c3d viewer` command that launches a local web server (FastAPI + React Three Fiber) to visualize the
result.12

- **Export Capabilities:** The documentation explicitly highlights **STL** management via a "Model Library".12 While
  explicit CLI flags for STEP export are not detailed in the snippets, the underlying engine is CadQuery. Therefore, the
  generated scripts _can_ produce STEP files. The limitation here is in the CLI wrapper, not the fundamental technology.
  Users proficient in Python can trivially modify the output script to save as `.step`.
- **Resource Usage:** The report notes that local inference requires significant RAM (~10GB), highlighting the trade-off
  between privacy/independence and hardware cost.11

### 2.4. Build123d and OpenSCAD: The Scripting Substrate

Repositories: openscad/openscad, gumyr/build123d
Role: Target Languages for AI Generation

It is essential to recognize that the _target languages_ themselves are open-source repositories that enable the entire
ecosystem.

- **OpenSCAD:** The veteran of programmatic CAD. While effective, its functional syntax (a unique domain-specific
  language) can be challenging for LLMs compared to standard Python. However, repositories like **SolidGen** and
  fine-tunes on "The Stack" have shown that LLMs can generate valid SCAD code.13
- **Build123d:** Emerging as a preferred target for AI generation. Its structure mimics human design logic (Sketch
  $\rightarrow$ Extrude $\rightarrow$ Fillet), which aligns well with the "Chain of Thought" reasoning patterns of
  advanced LLMs. The user can find specific examples of "AI-Build123d" integration in the **PartCAD** documentation and
  various GitHub discussions.7

---

## 3. The Sequence and Retrieval Paradigm: "Smart" Generation

Moving beyond direct text-to-code translation, a second cluster of repositories treats CAD generation as a sequence
prediction problem or employs advanced retrieval techniques (RAG) to construct models from known good sub-components.

### 3.1. Text2CAD: Sequential Geometric Prediction

Repository: SadilKhan/Text2CAD
Primary Output: Sequential Design History (Parametric)
Key Innovation: Transformer-based Auto-regressive Network

**Text2CAD** takes a more academic approach, viewing a CAD model not just as a final shape, but as a sequence of
operations. The model is trained to predict the next geometric operation (e.g., "Draw Circle at (0,0)", "Extrude 5mm")
based on the text prompt.15

- **DeepCAD Dataset:** This repository is closely linked to the **DeepCAD** dataset, a large-scale collection of CAD
  command sequences.
- **Capabilities:** By generating the _sequence_, Text2CAD ensures that the resulting model is editable. It preserves
  the "design intent." The repository provides the code for the "CadSeqProc" (CAD Sequence Processor) and the "
  Cad_VLM" (Vision Language Model) components.17
- **Relevance:** This is highly relevant for users who need _parametric_ outputs (STEP) but want a model architecture
  specifically designed for geometry, rather than repurposing a general code-writing LLM.

### 3.2. Seek-CAD: The Self-Refining RAG Framework

Repository: mii-laboratory/UniCAD (Note: UniCAD is medical, but Seek-CAD uses similar paradigms), Correction: Seek-CAD
is distinct.

Source: 18

**Seek-CAD** (Self-refined Generative Modeling for 3D Parametric CAD) represents the cutting edge of 2025 research. It
acknowledges that LLMs often hallucinate geometric constraints. To counter this, it introduces a **Retrieval-Augmented
Generation (RAG)** pipeline.18

- **Mechanism:** When a user prompts for a "flange," the system does not just guess the code. It retrieves relevant,
  validated CAD code snippets from a local corpus.
- **Visual Feedback Loop:** Uniquely, Seek-CAD implements a self-correction loop. It renders the generated code, passes
  the image to a Vision-Language Model (like Gemini or a local LLaVA), and asks: "Does this look like the user's
  prompt?" The feedback is used to refine the code iteratively before presenting the final result.
- **Open Source Status:** The paper references a GitHub repository (often tied to the authors Jiahao Li or the MII
  Laboratory), but availability can be fluid. The _methodology_, however, is fully documented for implementation by
  advanced peers.20

### 3.3. CADLLM: Industrial Automation

Repository: jianxliao/cadllm-page
Primary Output: Modeling Sequences
Key Innovation: Dual-Channel Feature Aggregation

**CADLLM** focuses on the "Detailed Design Phase" of industrial automation. It introduces a **TCADGen** (
Transformer-based CAD Generator) that aggregates features from both the textual parameters and the desired appearance
descriptions.21

- **Semi-Automated Annotation:** The project utilizes a pipeline where LLMs help annotate the training data, creating a
  high-quality feedback loop for training the generator.
- **Accuracy:** Experimental results claim it outperforms traditional methods in generating complex sequences.22 This
  repository is essential for users looking for an enterprise-grade, process-oriented solution rather than a hobbyist
  tool.

---

## 4. The Latent Diffusion Paradigm: Visual Assets and Meshes

While the previous sections focused on parametric precision (STEP), the most visually impressive advancements in AI have
occurred in the domain of **Mesh Generation**. These repositories utilize Latent Diffusion Models (LDMs) or Neural
Radiance Fields (NeRFs) to "grow" 3D geometry from text. While they excel at organic shapes (statues, characters,
furniture), they struggle with exact dimensions and typically output only **STL**, **OBJ**, or **PLY** files.

### 4.1. Hunyuan3D-2: The High-Fidelity Titan

Repository: Tencent-Hunyuan/Hunyuan3D-2
Primary Output: GLB, STL (via Trimesh)
Key Innovation: Two-Stage Generation (Shape + Texture)

Released by Tencent, **Hunyuan3D-2** is currently one of the most powerful open-source text-to-3D systems available. It
addresses the "blurry texture" problem of earlier models by separating the task into two stages: a DiT (Diffusion
Transformer) for geometry and a specialized paint module for texture.23

- **Open Source & Local:** The repository provides full inference code and pretrained checkpoints. It supports running
  locally (with significant VRAM, ~16GB recommended).23
- **Output Analysis:** The model generates **trimesh** objects. While the default export is often GLB (for web/AR), the
  underlying Python library allows trivial export to **STL**. However, the topology is a "soup of triangles." It is
  suitable for 3D printing (STL) but **not** for CNC machining or further CAD editing (STEP).23

### 4.2. Shap-E and Point-E: The Fast Inference Baseline

Repository: openai/shap-e
Primary Output: Implicit Functions $\rightarrow$ STL/PLY
Key Innovation: Latent Representation of Implicit Functions

**Shap-E** generates 3D objects as parameters of implicit functions, which can be rendered into meshes. It is
significantly faster than NeRF-based approaches, capable of generating a model in seconds on a single GPU.24

- **STL Support:** The repository includes a `text_to_3d` notebook that explicitly demonstrates converting the latent
  output into an STL file.26
- **Usage Profile:** Shap-E is ideal for rapid prototyping of non-functional parts. The geometry is often "soft" or "
  blobby," lacking the sharp edges required for mechanical assemblies. It is a strictly mesh-based workflow.

### 4.3. TRELLIS: The Scalable Structured Latent

Repository: microsoft/TRELLIS
Primary Output: Radiance Fields, Gaussians, Meshes (GLB/PLY)
Key Innovation: Unified Structured Latent (SLAT) Representation

**TRELLIS** represents the scale-up of 3D generation, utilizing models with up to 2 billion parameters.27 It offers
flexibility in output, supporting Radiance Fields for rendering and Meshes for export.

- **Capabilities:** It excels at high-quality assets with intricate details. However, like Hunyuan, it is a visual
  generator. It does not "know" that a table leg is a cylinder; it only knows that the volume looks like a cylinder.
  This limits its utility for the user's "STEP" requirement.

### 4.4. MeshGPT: Transformers for Geometry

Repository: lucidrains/meshgpt-pytorch
Primary Output: Compact Meshes (STL)
Key Innovation: Discrete Geometric Vocabulary

Unlike diffusion models that "denoise" a cloud of points, **MeshGPT** learns a vocabulary of geometric triangles. It
generates meshes autoregressively, token by token, similar to how GPT-4 generates text.28

- **Advantage:** This often results in cleaner topology (sharper edges, fewer artifacts) compared to diffusion-based
  meshes (Shap-E).
- **Status:** The `meshgpt-pytorch` repository by lucidrains is an open-source implementation of this paper, making it
  accessible for researchers to train their own models.30

---

## 5. Domain-Specific Clarifications: Medical vs. Industrial

In the course of research, several repositories with "CAD" in the title appear which cater to **Computer-Aided Diagnosis
** rather than Design. It is critical for the user to distinguish these to avoid false leads.

### 5.1. UniCAD: A Medical False Positive

Repository: mii-laboratory/UniCAD
Domain: Medical Imaging (Diagnosis)
Analysis: The snippets regarding UniCAD 31 describe a "unified architecture for multi-task computer-aided diagnosis." It
utilizes Vision Transformers to analyze 2D X-rays and 3D CT scans. While it handles "3D images," it is not a tool for
generating STL/STEP files for manufacturing. It is an analytical tool, not a generative design tool. This distinction is
vital for a user searching for "CAD designs."

---

## 6. The Bridge: Converting Mesh to STEP

A recurring theme in the analysis is the "Gap": easy-to-use AI models (Shap-E, Hunyuan) output STL, but professional
manufacturing requires STEP. Converting STL to STEP is mathematically non-trivial because it requires reconstructing
continuous surfaces from discrete triangles.

### 6.1. TheTesla/stl2step: Algorithmic Reconstruction

Repository: TheTesla/stl2step
Function: CLI Converter
Mechanism: Shape Segmentation

This repository is a critical utility for the user's workflow. It attempts to segment an STL mesh into basic geometric
primitives (planes, cylinders, spheres). If the AI generates a "hole," `stl2step` attempts to recognize the cylinder of
triangles and replace it with a true B-Rep cylinder.33

- **Utility:** This allows a user to take a **Shap-E** output (STL) and convert it into a **STEP** file that is somewhat
  editable in SolidWorks or Fusion360. It is an imperfect but necessary bridge.34

### 6.2. FreeCAD Scripting: The "Headless" Solver

Repositories: FreeCAD/FreeCAD, faerietree/freecad_convert
Function: Python-based Conversion
For a more robust, scriptable solution, **FreeCAD** offers a Python API that can be automated.

- **Workflow:**
   ```python
    import Part, Mesh
    mesh = Mesh.Mesh("generated_model.stl")
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tolerance=0.1)
    Part.export([shape], "converted_model.step")
    ```
- **Relevance:** Many "AI" repositories implicitly rely on this FreeCAD backend to handle file conversion. A user
  building a custom pipeline should consider FreeCAD's Python libraries as the "glue" layer.35

---

## 7. Comparative Analysis and Recommendations

The landscape of open-source text-to-CAD is not a single category but a spectrum of trade-offs between **Precision** (
STEP) and **Aesthetics** (STL).

### 7.1. Architectural Comparison Matrix

| **Feature**        | **Code-Centric (PartCAD, Text-to-CadQuery)** | **Sequence Prediction (Text2CAD)**      | **Latent Diffusion (Hunyuan, Shap-E)**   |
|--------------------|----------------------------------------------|-----------------------------------------|------------------------------------------|
| **Primary Output** | **STEP, STL**, 3MF                           | Design History (Parametric)             | **STL**, GLB, PLY                        |
| **Mechanism**      | LLM $\to$ Python Code $\to$ Kernel           | Transformer $\to$ Tokens $\to$ Geometry | Diffusion $\to$ Voxel/Point $\to$ Mesh   |
| **Precision**      | Exact (10.0mm is 10.0000...)                 | High (depends on tokenizer)             | Low (Approximated)                       |
| **Editability**    | High (Edit the script)                       | High (Edit the sequence)                | Low (Static Mesh)                        |
| **Best For**       | Mechanical Parts, Brackets, Gears            | Research, CAD History                   | Characters, Art, Organic Shapes          |
| **STEP Support**   | **Native**                                   | Native/Convertible                      | **Impossible** (requires ext. converter) |

### 7.2. Strategic Recommendations

**Scenario A: The Engineer (Needs STEP)**
For a user requiring functional, precise CAD models for manufacturing, the Code-Centric path is the only viable option.

- **Primary Tool:** **PartCAD**. Its integration of local LLMs (Ollama) and multiple kernels (Build123d/CadQuery) makes
  it the most "production-ready" open-source tool. It handles the dependencies and outputs STEP natively.
- **Model Source:** **Text-to-CadQuery**. The fine-tuned weights from this project should be used as the "brain" behind
  the PartCAD workflow to minimize syntax errors.

**Scenario B: The Prototyper (Needs STL)**
For a user requiring quick physical models or visual assets where tolerance is loose.

- **Primary Tool:** **Hunyuan3D-2**. It offers the highest fidelity among open-source mesh generators.
- **Secondary Tool:** **Shap-E**. For lower resource environments or faster iteration cycles.

**Scenario C: The Local-First/Privacy Advocate**

- **Primary Tool:** **C3D**. Its specific design around local inference (Ollama) ensures that no proprietary design
  prompts leave the local machine.

### 7.3. Conclusion

The open-source text-to-CAD ecosystem has matured significantly. While "Text-to-Mesh" (Shap-E, Hunyuan) has captured the
popular imagination with visual prowess, the "Text-to-Code" (Text-to-CadQuery, PartCAD) paradigm has quietly solved the
engineering challenge of generating precision STEP files. The convergence of these technologies—seen in "Hybrid" systems
like Seek-CAD—suggests a future where AI visualizes the design and then writes the code to construct it, satisfying both
the aesthetic and functional requirements of the user. For now, the user is best served by leveraging **PartCAD** for
infrastructure and **Text-to-CadQuery** for model intelligence.

## References

1. [Text-to-CadQuery: A New Paradigm for CAD Generation with Scalable Large Model Capabilities - arXiv](https://arxiv.org/html/2505.06507v1)
2. [Text-to-CadQuery: A New Paradigm for CAD Generation with Scalable Large Model Capabilities - arXiv](https://arxiv.org/pdf/2505.06507?)
3. [Paper page - Text-to-CadQuery: A New Paradigm for CAD Generation with Scalable Large Model Capabilities - Hugging Face](https://huggingface.co/papers/2505.06507)
4. [Package manager for things. Start designing modular hardware! PartCAD is the standard for documenting manufacturable physical products (a.k.a. Digital Thread or TDP). It comes with a set of tools to maintain product information and to facilitate efficient and effective workflows at all product lifecycle phases, boosted by AI. - GitHub](https://github.com/partcad/partcad)
5. [PartCAD - GitHub](https://github.com/partcad)
6. [partcad/partcad: Package manager for things. Start ... - GitHub](https://github.com/openvmp/partcad)
7. [Configuration — PartCAD Documentation - Read the Docs](https://partcad.readthedocs.io/en/latest/configuration.html)
8. [OpenSCAD is kinda neat - Hacker News](https://news.ycombinator.com/item?id=46337984)
9. [Build123d and Cadquery procedural CAD output and input support](https://news.ycombinator.com/item?id=44189323)
10. [PartCAD - Putting all parts together](https://partcad.org/)
11. [C3D-v0: AI-Powered CAD Code Generation Model - Ollama](https://ollama.com/joshuaokolo/C3Dv0)
12. [unxversal/c3d: Cxmpute 3D Lab - GitHub](https://github.com/unxversal/c3d)
13. [OpenSCAD - The Programmers Solid 3D CAD Modeller - GitHub](https://github.com/openscad/openscad)
14. [Show HN: GPT image editing, but for 3D models | Hacker News](https://news.ycombinator.com/item?id=44182206)
15. [Text2CAD: Generating Sequential CAD Designs from Beginner-to-Expert Level Text Prompts - NIPS papers](https://papers.nips.cc/paper_files/paper/2024/hash/0e5b96f97c1813bb75f6c28532c2ecc7-Abstract-Conference.html)
16. [Text2CAD: Generating Sequential CAD Models from Beginner-to-Expert Level Text Prompts](https://www.dfki.de/en/web/research/projects-and-publications/publication/15570)
17. [SadilKhan/Text2CAD: [NeurIPS'24 Spotlight] Text2CAD ... - GitHub](https://github.com/SadilKhan/Text2CAD)
18. [Seek-CAD: A Self-refined Generative Modeling for 3D Parametric CAD Using Local Inference via DeepSeek - arXiv](https://arxiv.org/html/2505.17702v1)
19. [CADDesigner: Conceptual Design of CAD Models Based on General-Purpose Agent - arXiv](https://arxiv.org/html/2508.01031v1)
20. [Seek-CAD: A Self-refined Generative Modeling for 3D Parametric CAD Using Local Inference via DeepSeek - arXiv](https://arxiv.org/abs/2505.17702)
21. [Automated CAD Modeling Sequence Generation from Text Descriptions](https://jianxliao.github.io/cadllm-page/)
22. [Automated CAD Modeling Sequence Generation from Text Descriptions via Transformer-Based Large Language Models - ResearchGate](https://www.researchgate.net/publication/392104203_Automated_CAD_Modeling_Sequence_Generation_from_Text_Descriptions_via_Transformer-Based_Large_Language_Models)
23. [Tencent-Hunyuan/Hunyuan3D-2: High-Resolution 3D ... - GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
24. [openai/shap-e: Generate 3D objects conditioned on text or images - GitHub](https://github.com/openai/shap-e)
25. [Point-E: A system for generating 3D point clouds from complex prompts | OpenAI](https://openai.com/index/point-e/)
26. [Shape-E Tutorial: how to set up and use Shap-E model - Lablab.ai](https://lablab.ai/t/shape-e-tutorial-how-to-set-up-and-use-shap-e-model)
27. [microsoft/TRELLIS: Official repo for paper "Structured 3D ... - GitHub](https://github.com/microsoft/TRELLIS)
28. [MeshGPT: Generating Triangle Meshes with Decoder-Only Transformers - Yawar Siddiqui](https://nihalsid.github.io/mesh-gpt/)
29. [MeshGPT: Generating Triangle Meshes with Decoder-Only Transformers | Request PDF](https://www.researchgate.net/publication/384234159_MeshGPT_Generating_Triangle_Meshes_with_Decoder-Only_Transformers)
30. [Training guide · lucidrains meshgpt-pytorch · Discussion #51 - GitHub](https://github.com/lucidrains/meshgpt-pytorch/discussions/51)
31. [Towards a Unified Framework of Clustering-based Anomaly Detection - GitHub](https://raw.githubusercontent.com/mlresearch/v267/main/assets/fang25d/fang25d.pdf)
32. [Related papers: UniCAD: Efficient and Extendable Architecture for](https://fugumt.com/fugumt/paper_check/2505.09178v2_enmode)
33. [TheTesla/stl2step: intelligent approach to convert stl files into step files - GitHub](https://github.com/TheTesla/stl2step)
34. [Conversion of STL file (or binary mask) to STEP file with NURBS or minimal surface patches : r/AskEngineers - Reddit](https://www.reddit.com/r/AskEngineers/comments/1opwsa3/conversion_of_stl_file_or_binary_mask_to_step/)
35. [stl2step FreeCAD script - Reddit](https://www.reddit.com/r/FreeCAD/comments/lhvro5/stl2step_freecad_script/)
36. [Python scripting tutorial - FreeCAD Documentation](https://wiki.freecad.org/Python_scripting_tutorial)