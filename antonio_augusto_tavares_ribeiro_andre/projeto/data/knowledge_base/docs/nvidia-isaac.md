# NVIDIA Isaac

NVIDIA Isaac é a plataforma de robótica e IA física da NVIDIA, cobrindo simulação,
treinamento e deploy de robôs autônomos e sistemas de percepção. Integra-se a Omniverse para
simulação e roda nos módulos Jetson no edge.

## Componentes
- **Isaac Sim**: simulação robótica fisicamente precisa sobre Omniverse, para testar e gerar
  dados sintéticos sem hardware real.
- **Isaac ROS**: pacotes GPU-acelerados de percepção (visão, SLAM, manipulação) compatíveis
  com ROS 2.
- **Isaac Lab / GR00T**: treinamento de políticas (RL, imitation learning) e modelos
  fundacionais para robôs humanoides.
- **Deploy no edge**: execução nos sistemas Jetson com inferência otimizada.

## Quando recomendar
Indicado para startups de **robótica, automação física e manufatura inteligente** que
precisam treinar e validar agentes em simulação antes de operar no mundo real. É uma
tecnologia de domínio (junto de Omniverse e GPUs): o TAPI a recomenda quando o perfil pede
robótica/simulação, mas não a dogfooda.
