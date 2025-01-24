import pickle
import sys
import pygame
from pygame.locals import *
import neat
import os

import visualize
from constants import *
from pacman import Pacman
from nodes import NodeGroup
from pellets import PelletGroup
from ghosts import GhostGroup
from fruit import Fruit
from pauser import Pause
from text import TextGroup
from sprites import LifeSprites
from sprites import MazeSprites
from mazedata import MazeData
import multiprocessing


class GameController(object):
    def __init__(self, train_mode=False, net=None, config=None, headless=False, fixed_dt=1.0/60.0):
        """
        :param train_mode: se True, la partita viene gestita in modalità training (senza input utente).
        :param net: rete neurale di NEAT (solo in modalità training).
        :param config: configurazione NEAT (opzionale, in caso serva).
        :param headless: se True, non viene effettuato il rendering (accelerazione massima).
        :param fixed_dt: delta time fisso da utilizzare in modalità headless.
        """
        self.headless = headless
        self.fixed_dt = fixed_dt
        self.train_mode = train_mode
        self.net = net
        self.neat_config = config
        self.game_over = False  # Per sapere se la partita è terminata in modalità training

        # Inizializziamo pygame solo se NON headless, altrimenti evitiamo
        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
        else:
            # In headless non creiamo finestra, ma inizializziamo comunque pygame
            pygame.init()
            self.screen = None

        self.background = None
        self.background_norm = None
        self.background_flash = None

        # Se non siamo in headless, usiamo un clock per stabilire un framerate "umano".
        # In headless, skip.
        if not self.headless:
            self.clock = pygame.time.Clock()
        else:
            self.clock = None

        self.fruit = None
        self.pause = Pause(not train_mode)
        self.level = 0
        self.lives = 0
        self.score = 0
        self.textgroup = TextGroup()
        self.lifesprites = LifeSprites(self.lives)
        self.flashBG = False
        self.flashTime = 0.2
        self.flashTimer = 0
        self.fruitCaptured = []
        self.fruitNode = None
        self.mazedata = MazeData()

    def setBackground(self):
        self.background_norm = pygame.surface.Surface(SCREENSIZE).convert()
        self.background_norm.fill(BLACK)
        self.background_flash = pygame.surface.Surface(SCREENSIZE).convert()
        self.background_flash.fill(BLACK)
        self.background_norm = self.mazesprites.constructBackground(self.background_norm, self.level % 5)
        self.background_flash = self.mazesprites.constructBackground(self.background_flash, 5)
        self.flashBG = False
        self.background = self.background_norm

    def startGame(self):
        self.mazedata.loadMaze(self.level)
        self.mazesprites = MazeSprites(self.mazedata.obj.name + ".txt",
                                       self.mazedata.obj.name + "_rotation.txt")
        self.setBackground()
        self.nodes = NodeGroup(self.mazedata.obj.name + ".txt")
        self.mazedata.obj.setPortalPairs(self.nodes)
        self.mazedata.obj.connectHomeNodes(self.nodes)

        # Creiamo l'istanza di Pacman
        # In modalità training, useremo la logica AI interna (override del getValidKey).
        self.pacman = Pacman(self.nodes.getNodeFromTiles(*self.mazedata.obj.pacmanStart),
                             train_mode=self.train_mode,
                             net=self.net,
                             config=self.neat_config)

        self.pellets = PelletGroup(self.mazedata.obj.name + ".txt")
        self.ghosts = GhostGroup(self.nodes.getStartTempNode(), self.pacman)

        self.ghosts.pinky.setStartNode(self.nodes.getNodeFromTiles(*self.mazedata.obj.addOffset(2, 3)))
        self.ghosts.inky.setStartNode(self.nodes.getNodeFromTiles(*self.mazedata.obj.addOffset(0, 3)))
        self.ghosts.clyde.setStartNode(self.nodes.getNodeFromTiles(*self.mazedata.obj.addOffset(4, 3)))
        self.ghosts.setSpawnNode(self.nodes.getNodeFromTiles(*self.mazedata.obj.addOffset(2, 3)))
        self.ghosts.blinky.setStartNode(self.nodes.getNodeFromTiles(*self.mazedata.obj.addOffset(2, 0)))

        self.nodes.denyHomeAccess(self.pacman)
        self.nodes.denyHomeAccessList(self.ghosts)
        self.ghosts.inky.startNode.denyAccess(RIGHT, self.ghosts.inky)
        self.ghosts.clyde.startNode.denyAccess(LEFT, self.ghosts.clyde)
        self.mazedata.obj.denyGhostsAccess(self.ghosts, self.nodes)

        if self.train_mode:
            # In training, nessuna pausa iniziale
            self.pause.paused = False
            self.textgroup.hideText()

    def update(self):
        # Calcola dt in base alla modalità (headless o meno)
        if not self.headless:
            # Modalità visuale
            dt = self.clock.tick(60) / 1000.0
        else:
            # Modalità headless: dt fisso
            dt = self.fixed_dt

        self.textgroup.update(dt)
        self.pellets.update(dt)

        # Se il gioco è in pausa, fermiamo certe logiche
        if not self.pause.paused:
            self.ghosts.update(dt)
            if self.fruit is not None:
                self.fruit.update(dt)

            self.checkPelletEvents()
            self.checkGhostEvents()
            self.checkFruitEvents()

        if self.pacman.alive:
            if not self.pause.paused:
                self.pacman.update(dt)
        else:
            # Pacman morto
            self.pacman.update(dt)

        if self.flashBG:
            self.flashTimer += dt
            if self.flashTimer >= self.flashTime:
                self.flashTimer = 0
                if self.background == self.background_norm:
                    self.background = self.background_flash
                else:
                    self.background = self.background_norm

        afterPauseMethod = self.pause.update(dt)
        if afterPauseMethod is not None:
            afterPauseMethod()

        self.checkEvents()

        # Verifichiamo se dobbiamo terminare la partita in training
        if self.train_mode:
            # Esempio: consideriamo partita finita se Pacman non è vivo o se ha finito le vite
            if not self.pacman.alive or self.lives < 0:
                self.game_over = True

        # In modalità headless, niente rendering a schermo
        if not self.headless:
            self.render()

    def checkEvents(self):
        # In modalità train_mode si evita di gestire input utente
        if not self.train_mode:
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == KEYDOWN:
                    if event.key == K_SPACE:
                        if self.pacman.alive:
                            self.pause.setPause(playerPaused=True)
                            if not self.pause.paused:
                                self.textgroup.hideText()
                                self.showEntities()
                            else:
                                self.textgroup.showText(PAUSETXT)
        else:
            # In headless/training, gestiamo comunque un eventuale QUIT
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()

    def checkPelletEvents(self):
        pellet = self.pacman.eatPellets(self.pellets.pelletList)
        if pellet:
            self.pellets.numEaten += 1
            self.updateScore(pellet.points)
            if self.pellets.numEaten == 30:
                self.ghosts.inky.startNode.allowAccess(RIGHT, self.ghosts.inky)
            if self.pellets.numEaten == 70:
                self.ghosts.clyde.startNode.allowAccess(LEFT, self.ghosts.clyde)
            self.pellets.pelletList.remove(pellet)
            if pellet.name == POWERPELLET:
                self.ghosts.startFreight()
            if self.pellets.isEmpty():
                # Fine livello (vittoria). Per semplicità, chiudiamo il gioco.
                if self.train_mode:
                    self.game_over = True
                else:
                    pygame.quit()
                    sys.exit()

    def checkGhostEvents(self):
        for ghost in self.ghosts:
            if self.pacman.collideGhost(ghost):
                if ghost.mode.current is FREIGHT:
                    self.pacman.visible = False
                    ghost.visible = False
                    self.updateScore(ghost.points)
                    self.textgroup.addText(str(ghost.points), WHITE,
                                           ghost.position.x, ghost.position.y,
                                           8, time=1)
                    self.ghosts.updatePoints()
                    self.pause.setPause(pauseTime=1, func=self.showEntities)
                    ghost.startSpawn()
                    self.nodes.allowHomeAccess(ghost)
                elif ghost.mode.current is not SPAWN:
                    if self.pacman.alive:
                        self.lives -= 1
                        self.lifesprites.removeImage()
                        self.pacman.die()
                        self.ghosts.hide()
                        if self.lives <= 0:
                            self.textgroup.showText(GAMEOVERTXT)
                            if self.train_mode:
                                self.game_over = True
                            else:
                                self.pause.setPause(pauseTime=3,
                                                    func=self.restartGame)
                        else:
                            self.pause.setPause(pauseTime=3, func=self.resetLevel)

    def checkFruitEvents(self):
        if self.pellets.numEaten == 50 or self.pellets.numEaten == 140:
            if self.fruit is None:
                self.fruit = Fruit(self.nodes.getNodeFromTiles(9, 20),
                                   self.level)
        if self.fruit is not None:
            if self.pacman.collideCheck(self.fruit):
                self.updateScore(self.fruit.points)
                self.textgroup.addText(str(self.fruit.points), WHITE,
                                       self.fruit.position.x, self.fruit.position.y,
                                       8, time=1)
                fruitCaptured = False
                for fruit in self.fruitCaptured:
                    if fruit.get_offset() == self.fruit.image.get_offset():
                        fruitCaptured = True
                        break
                if not fruitCaptured:
                    self.fruitCaptured.append(self.fruit.image)
                self.fruit = None
            elif self.fruit.destroy:
                self.fruit = None

    def showEntities(self):
        self.pacman.visible = True
        self.ghosts.show()

    def hideEntities(self):
        self.pacman.visible = False
        self.ghosts.hide()

    def nextLevel(self):
        self.showEntities()
        self.level += 1
        self.pause.paused = True
        self.startGame()
        self.textgroup.updateLevel(self.level)

    def restartGame(self):
        self.lives = 0
        self.level = 0
        self.pause.paused = True
        self.fruit = None
        self.startGame()
        self.score = 0
        self.textgroup.updateScore(self.score)
        self.textgroup.updateLevel(self.level)
        self.textgroup.showText(READYTXT)
        self.lifesprites.resetLives(self.lives)
        self.fruitCaptured = []

    def resetLevel(self):
        self.pause.paused = True
        self.pacman.reset()
        self.ghosts.reset()
        self.fruit = None
        self.textgroup.showText(READYTXT)

    def updateScore(self, points):
        self.score += points
        self.textgroup.updateScore(self.score)

    def render(self):
        # In modalità headless, non disegniamo niente
        if self.headless:
            return

        self.screen.blit(self.background, (0, 0))
        self.pellets.render(self.screen)
        if self.fruit is not None:
            self.fruit.render(self.screen)
        self.pacman.render(self.screen)
        self.ghosts.render(self.screen)
        self.textgroup.render(self.screen)

        for i in range(len(self.lifesprites.images)):
            x = self.lifesprites.images[i].get_width() * i
            y = SCREENHEIGHT - self.lifesprites.images[i].get_height()
            self.screen.blit(self.lifesprites.images[i], (x, y))

        for i in range(len(self.fruitCaptured)):
            x = SCREENWIDTH - self.fruitCaptured[i].get_width() * (i + 1)
            y = SCREENHEIGHT - self.fruitCaptured[i].get_height()
            self.screen.blit(self.fruitCaptured[i], (x, y))

        pygame.display.update()


###############################################################################
#                        FUNZIONI DI TRAINING NEAT                             #
###############################################################################

def eval_genomes_visual(genomes, config):
    """
    Funzione di valutazione GENOMI in modalità VISUALE e SEQUENZIALE (lenta).
    """
    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        game = GameController(train_mode=True, net=net, config=config,
                              headless=False)  # headless=False => rendering
        game.startGame()

        while not game.game_over:
            game.update()

        genome.fitness = game.score


def eval_genomes_headless(genomes, config):
    """
    Funzione di valutazione GENOMI in modalità HEADLESS (dt fisso e loop veloce).
    Sequenziale (non parallela). Se vuoi parallelizzare, vedi `evaluate_single_genome` e `ParallelEvaluator`.
    """
    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        # Impostiamo headless=True e dt fisso (1/60.0 di default)
        game = GameController(train_mode=True, net=net, config=config,
                              headless=True, fixed_dt=1.0/60.0)
        game.startGame()

        while not game.game_over:
            game.update()

        genome.fitness = game.score


def evaluate_single_genome(genome, config):
    """
    Funzione di valutazione di un singolo genome, utile per la parallelizzazione.
    """
    net = neat.nn.FeedForwardNetwork.create(genome, config)
    game = GameController(train_mode=True, net=net, config=config,
                          headless=True, fixed_dt=1.0/60.0)
    game.startGame()

    while not game.game_over:
        game.update()

    return game.score


def run_neat_visual(config_file):
    """
    Avvia il training in modalità VISUALE e SEQUENZIALE (più lento).
    """
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_file)

    p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    # Eseguiamo fino a 100 generazioni, valutando i genomi in modalità visiva
    winner = p.run(eval_genomes_visual, 100)

    with open("winner.pkl", "wb") as f:
        pickle.dump(winner, f)

    print('\nBest genome:\n{!s}'.format(winner))
    visualize.plot_stats(stats, ylog=False, view=True)
    visualize.draw_net(config, winner, True)


def run_neat_headless_sequential(config_file):
    """
    Avvia il training in modalità HEADLESS ma sequenziale.
    """
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_file)

    p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    # Eseguiamo fino a 100 generazioni in headless (nessun rendering)
    winner = p.run(eval_genomes_headless, 100)

    with open("winner.pkl", "wb") as f:
        pickle.dump(winner, f)

    print('\nBest genome:\n{!s}'.format(winner))
    visualize.plot_stats(stats, ylog=False, view=True)
    visualize.draw_net(config, winner, True)


def run_neat_headless_parallel(config_file):
    """
    Avvia il training in modalità HEADLESS e PARALLELIZZATA,
    sfruttando tutti i core della CPU tramite ParallelEvaluator.
    """
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_file)

    p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    # ParallelEvaluator richiede una funzione che valuti SINGOLI genomi
    pe = neat.ParallelEvaluator(multiprocessing.cpu_count(), evaluate_single_genome)
    winner = p.run(pe.evaluate, 100)

    with open("winner.pkl", "wb") as f:
        pickle.dump(winner, f)

    print('\nBest genome:\n{!s}'.format(winner))
    visualize.plot_stats(stats, ylog=False, view=True)
    visualize.draw_net(config, winner, True)


def replay_genome(config_file, genome_path="winner.pkl"):
    # Load required NEAT config
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                config_file)

    # Unpickle saved winner
    with open(genome_path, "rb") as f:
        genome = pickle.load(f)

    # Convert loaded genome into required data structure
    genomes = [(1, genome)]

    # Draw the NN structure
    visualize.draw_net(config, genome, True)

    # Chiamiamo la funzione di valutazione, ad esempio in modalità headless
    eval_genomes_headless(genomes, config)


###############################################################################
#                           AVVIO DELLO SCRIPT                                #
###############################################################################

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "neat-config.txt")

    print("************************************")
    print("     Pac-ManAI v1.0    ")
    print("************************************")

    print("Allenare una AI con NEAT (1)")
    print("Giocare manualmente (2)")
    print("Far giocare l'AI (3)")
    choice = input("Input: ")

    if choice == "1":
        if not os.path.exists(config_path):
            print("Non trovo il file di configurazione NEAT (neat-config.txt).")
            sys.exit(1)

        print("\nSeleziona la modalità di training:")
        print("1) Modalità visiva e sequenziale (rallentata, con rendering).")
        print("2) Modalità headless sequenziale (niente rendering, dt fisso).")
        print("3) Modalità headless parallelizzata (niente rendering, dt fisso, usa tutti i core).")
        train_choice = input("Scelta: ")

        if train_choice == "1":
            run_neat_visual(config_path)
        elif train_choice == "2":
            run_neat_headless_sequential(config_path)
        elif train_choice == "3":
            run_neat_headless_parallel(config_path)
        else:
            print("Scelta non valida.")
            sys.exit(1)

    elif choice == "2":
        # Avvia il gioco manuale
        game = GameController()
        game.startGame()
        while True:
            game.update()

    elif choice == "3":
        try:
            replay_genome(config_path)
        except:
            print('Non trovo il file "winner.pkl" nella directory o è stato rinominato.')
            print('Se lo hai rinominato, ripristina il nome in "winner.pkl" per testare correttamente.')
            close = input('Premi Invio per uscire...')
            sys.exit()
    else:
        print("Scelta non valida.")
        sys.exit()
