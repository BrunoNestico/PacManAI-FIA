import pygame
from pygame.constants import K_UP, K_DOWN, K_LEFT, K_RIGHT
from vector import Vector2
from constants import *
from entity import Entity
from sprites import PacmanSprites


class Pacman(Entity):
    def __init__(self, startNode):
        super().__init__(startNode)
        self.name = PACMAN
        self.directions = {
            STOP: Vector2(),
            UP: Vector2(0, -1),
            DOWN: Vector2(0, 1),
            LEFT: Vector2(-1, 0),
            RIGHT: Vector2(1, 0)
        }
        self.speed = 100 * TILEWIDTH / 16
        self.color = YELLOW

        # Direzione iniziale (puoi cambiare se preferisci)
        self.direction = LEFT
        self.target = startNode
        self.alive = True

        # Raggio collisione
        self.radius = 10
        self.collideRadius = 5

        # Sprite
        self.sprites = PacmanSprites(self)
        # Imposta posizione iniziale esattamente al nodo di partenza
        self.setPosition()

    def setPosition(self):
        """Allinea Pac-Man al centro del suo nodo corrente."""
        self.position = self.node.position.copy()

    def reset(self):
        """Reset dello stato di Pac-Man."""
        Entity.reset(self)
        self.direction = LEFT
        self.target = self.node
        self.alive = True
        self.setPosition()
        self.sprites.reset()

    def die(self):
        """Pac-Man muore: azzera la direzione."""
        self.alive = False
        self.direction = STOP

    def update(self, dt, use_ai=False):
        """Updates Pac-Man's position and direction, ensuring no 'stuck' behavior."""
        self.sprites.update(dt)

        # 1) Determine the desired direction (from AI or keyboard)
        if not use_ai:
            desired_dir = self.getKeyDirection()
        else:
            desired_dir = self.direction  # Default to the current direction if no input

        # 2) Calculate movement for this frame
        distance_to_travel = self.speed * dt

        # 3) Ensure momentum by only allowing valid direction changes
        if self.validDirection(desired_dir) and desired_dir != STOP:
            self.direction = desired_dir  # Update direction only if valid and not STOP

        # 4) Process movement until all leftover distance is consumed
        while distance_to_travel > 0.0:
            dist_to_target = (self.target.position - self.position).magnitude()

            if dist_to_target <= 0.0001:
                # Reached the center of the current target node
                self.node = self.target

                # Check for portals and move through if applicable
                if self.node.neighbors[PORTAL] is not None:
                    self.node = self.node.neighbors[PORTAL]
                    self.position = self.node.position.copy()

                # Try to continue in the current direction or set a new valid direction
                next_target = self.getNewTarget(self.direction)
                if next_target is not self.node:
                    self.target = next_target
                else:
                    # If the current direction is blocked, stop or try to keep moving
                    self.direction = STOP
                    break
            else:
                # If not at the center of the target, move towards it
                if dist_to_target <= distance_to_travel:
                    self.position = self.target.position.copy()
                    distance_to_travel -= dist_to_target
                else:
                    direction_vector = (self.target.position - self.position).normalize()
                    self.position += direction_vector * distance_to_travel
                    distance_to_travel = 0.0



    def getKeyDirection(self):
        """Return the desired direction based on pressed keys."""
        keys = pygame.key.get_pressed()
        if keys[K_UP]:
            return UP
        if keys[K_DOWN]:
            return DOWN
        if keys[K_LEFT]:
            return LEFT
        if keys[K_RIGHT]:
            return RIGHT
        return STOP

    def validDirection(self, direction):
        """Check if there's a neighboring node in the requested direction that Pacman can access."""
        if direction != STOP and self.node is not None:
            neighbor = self.node.neighbors.get(direction)
            if neighbor is not None and PACMAN in self.node.access[direction]:
                return True
        return False

    def getNewTarget(self, direction):
        """Ritorna il nodo se esiste nella direzione richiesta, altrimenti l’attuale nodo."""
        if self.validDirection(direction):
            return self.node.neighbors[direction]
        return self.node

    def eatPellets(self, pelletList):
        """Controlla collisioni con i pellet."""
        for pellet in pelletList:
            if self.collideCheck(pellet):
                return pellet
        return None

    def collideGhost(self, ghost):
        """Controlla collisione con un fantasma."""
        return self.collideCheck(ghost)

    def collideCheck(self, other):
        """Rilevamento collisione in base ai raggi."""
        d = self.position - other.position
        dSquared = d.magnitudeSquared()
        rSquared = (self.collideRadius + other.collideRadius) ** 2
        return dSquared <= rSquared