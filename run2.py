import pygame
from pygame.locals import *
from constants import *
from pacman import Pacman
from nodes import NodeGroup
from pellets import PelletGroup
from ghosts import GhostGroup
from fruit import Fruit
from pauser import Pause
from text import TextGroup

class GameController(object):
    def __init__(self, updates_per_frame=10):
        """ Inizializza il gioco in modalità veloce con stampa in console """
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)  # Display "off-screen" per evitare errori grafici

        self.clock = pygame.time.Clock()
        self.fruit = None
        self.pause = Pause(True)
        self.level = 0
        self.lives = 5
        self.score = 0
        self.textgroup = TextGroup()
        self.updates_per_frame = updates_per_frame  # Numero di aggiornamenti per frame

        print(f"[INFO] Gioco avviato - Vite iniziali: {self.lives}, Livello: {self.level}")

    def restartGame(self):
        """ Riavvia il gioco quando il giocatore perde tutte le vite """
        self.lives = 5
        self.level = 0
        self.pause.paused = True
        self.fruit = None
        self.startGame()
        self.score = 0
        self.textgroup.updateScore(self.score)
        self.textgroup.updateLevel(self.level)
        print("[RESET] Gioco riavviato")

    def startGame(self):
        """ Inizializza una nuova partita """
        self.nodes = NodeGroup("maze1.txt")
        self.nodes.setPortalPair((0, 17), (27, 17))
        self.pacman = Pacman(self.nodes.getNodeFromTiles(15, 26))
        self.pellets = PelletGroup("maze1.txt")
        self.ghosts = GhostGroup(self.nodes.getStartTempNode(), self.pacman)
        print(f"[NEW GAME] Iniziato livello {self.level}")

    def update(self):
        """ Aggiorna il gioco più volte per ciclo per massimizzare la velocità """
        dt = 0.001  # Fisso un piccolo delta time per la simulazione

        for _ in range(self.updates_per_frame):  # Esegui più aggiornamenti per frame
            self.textgroup.update(dt)
            self.pellets.update(dt)
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
                self.pacman.update(dt)

            afterPauseMethod = self.pause.update(dt)
            if afterPauseMethod is not None:
                afterPauseMethod()

            self.checkEvents()

        print(f"[UPDATE] Frame aggiornato ({self.updates_per_frame} updates per frame) - Score: {self.score}")

    def checkEvents(self):
        """ Controlla gli eventi della tastiera """
        for event in pygame.event.get():
            if event.type == QUIT:
                exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    if self.pacman.alive:
                        self.pause.setPause(playerPaused=True)
                        print("[PAUSE] Gioco in pausa")

    def checkFruitEvents(self):
        """ Controlla se la frutta deve apparire o essere raccolta """
        if self.pellets.numEaten == 50 or self.pellets.numEaten == 140:
            if self.fruit is None:
                self.fruit = Fruit(self.nodes.getNodeFromTiles(9, 20))
                print("[FRUIT] Frutta apparsa!")

        if self.fruit is not None:
            if self.pacman.collideCheck(self.fruit):
                self.score += self.fruit.points
                print(f"[FRUIT] Pac-Man ha mangiato la frutta! Score: {self.score}")
                self.fruit = None  # Rimuove la frutta dopo essere stata raccolta
            elif self.fruit.destroy:
                self.fruit = None
                print("[FRUIT] Frutta scomparsa")

    def checkPelletEvents(self):
        """ Controlla se Pac-Man ha mangiato un pellet """
        pellet = self.pacman.eatPellets(self.pellets.pelletList)
        if pellet:
            self.pellets.numEaten += 1
            self.score += pellet.points
            self.pellets.pelletList.remove(pellet)
            print(f"[PELLET] Pac-Man ha mangiato un pellet - Score: {self.score}, Pellets restanti: {len(self.pellets.pelletList)}")

            if self.pellets.isEmpty():
                self.level += 1
                print(f"[LEVEL UP] Pac-Man ha completato il livello! Nuovo livello: {self.level}")
                self.pause.setPause(pauseTime=3, func=self.startGame)

    def checkGhostEvents(self):
        """ Controlla le collisioni tra Pac-Man e i fantasmi """
        for ghost in self.ghosts:
            if self.pacman.collideGhost(ghost):
                if ghost.mode.current is FREIGHT:
                    self.pacman.visible = False
                    ghost.visible = False
                    self.score += ghost.points
                    print(f"[GHOST] Pac-Man ha mangiato un fantasma! Score: {self.score}")
                    self.ghosts.updatePoints()
                    ghost.startSpawn()
                elif ghost.mode.current is not SPAWN:
                    if self.pacman.alive:
                        self.lives -= 1
                        print(f"[HIT] Pac-Man è stato colpito da un fantasma! Vite rimanenti: {self.lives}")
                        self.pacman.die()
                        if self.lives <= 0:
                            print("[GAME OVER] Pac-Man ha perso tutte le vite!")
                            self.pause.setPause(pauseTime=3, func=self.restartGame)
                        else:
                            self.pause.setPause(pauseTime=3, func=self.startGame)

if __name__ == "__main__":
    game = GameController(updates_per_frame=20)  # 🚀 Velocizza il training aumentando gli aggiornamenti per frame!
    game.startGame()
    while True:
        game.update()
 