import pygame
from pygame.locals import *
from vector import Vector2
from constants import *
from entity import Entity
from sprites import PacmanSprites
import random

class Pacman(Entity):
    def __init__(self, node, train_mode=False, net=None, config=None):
        """
        :param node: Nodo iniziale di Pacman.
        :param train_mode: True se stiamo allenando l'AI con NEAT (nessun input da tastiera).
        :param net: rete neurale corrispondente al genome in valutazione.
        :param config: configurazione NEAT (opzionale, nel caso volessimo usarla).
        """
        Entity.__init__(self, node)
        self.name = PACMAN
        self.color = YELLOW
        self.direction = LEFT
        self.setBetweenNodes(LEFT)
        self.alive = True
        self.sprites = PacmanSprites(self)

        # Variabili per la modalità training
        self.train_mode = train_mode
        self.net = net
        self.neat_config = config

    def reset(self):
        Entity.reset(self)
        self.direction = LEFT
        self.setBetweenNodes(LEFT)
        self.alive = True
        self.image = self.sprites.getStartImage()
        self.sprites.reset()

    def die(self):
        self.alive = False
        self.direction = STOP

    def update(self, dt):
        self.sprites.update(dt)
        self.position += self.directions[self.direction]*self.speed*dt

        # Invece di prendere input da tastiera, in train_mode prendiamo la mossa dalla rete neurale
        direction = self.getValidKey() if not self.train_mode else self.getValidKeyAI()

        if self.overshotTarget():
            self.node = self.target
            if self.node.neighbors[PORTAL] is not None:
                self.node = self.node.neighbors[PORTAL]
            self.target = self.getNewTarget(direction)
            if self.target is not self.node:
                self.direction = direction
            else:
                self.target = self.getNewTarget(self.direction)

            if self.target is self.node:
                self.direction = STOP
            self.setPosition()
        else:
            if self.oppositeDirection(direction):
                self.reverseDirection()

    def getValidKey(self):
        key_pressed = pygame.key.get_pressed()
        if key_pressed[K_UP]:
            return UP
        if key_pressed[K_DOWN]:
            return DOWN
        if key_pressed[K_LEFT]:
            return LEFT
        if key_pressed[K_RIGHT]:
            return RIGHT
        return STOP

    def getValidKeyAI(self):
        """
        Esempio minimal di come potremmo scegliere un'azione dalla rete neurale.
        NOTA: in un caso reale, bisognerebbe definire quali input passare alla rete
        (posizione Pacman, posizione Ghosts, distanza dai muri, ecc.) e interpretare l'output.
        Per ora, facciamo solo una scelta casuale se la rete non è definita.
        """
        if self.net is None:
            # Se la rete non è definita, muoviamoci random
            return random.choice([UP, DOWN, LEFT, RIGHT, STOP])
        else:
            # Esempio di input fittizio [0,0,0,0].
            # Andrebbe sostituito con dati reali sullo stato di gioco.
            input_data = [0.0, 0.0, 0.0, 0.0]
            output = self.net.activate(input_data)
            # Supponiamo che la rete abbia 4 output corrispondenti a [UP, DOWN, LEFT, RIGHT]
            # e scegliamo il massimo.
            # Se la dimensione è diversa, regolare di conseguenza.
            if len(output) < 4:
                return random.choice([UP, DOWN, LEFT, RIGHT, STOP])
            move_index = output.index(max(output))  # indice dell'output più alto
            if move_index == 0:
                return UP
            elif move_index == 1:
                return DOWN
            elif move_index == 2:
                return LEFT
            elif move_index == 3:
                return RIGHT
            return STOP

    def eatPellets(self, pelletList):
        for pellet in pelletList:
            if self.collideCheck(pellet):
                return pellet
        return None

    def collideGhost(self, ghost):
        return self.collideCheck(ghost)

    def collideCheck(self, other):
        d = self.position - other.position
        dSquared = d.magnitudeSquared()
        rSquared = (self.collideRadius + other.collideRadius)**2
        if dSquared <= rSquared:
            return True
        return False
